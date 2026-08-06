"""Halite tournament bot, fourth generation (experiment record).

Started as a different architecture from bot2's greedy auction, borrowing
from the published Halite IV playbook (0Zeta's 4th-place writeup,
solverworld's optimal-mining notebook). Head-to-head series against bot2
rejected most of the new ideas, so the shipped configuration is bot2's
economics plus the two survivors -- see docs/bot4.md for the full
experiment log.

Active differences from bot2:

  * Endgame convert: a ship carrying well over the convert cost that can't
    reach home in the turns remaining converts in place, banking cargo
    minus 500 that would otherwise evaporate at turn 400.
  * Kill moves: stepping onto a heavier enemy ship scores a small movement
    bonus (we win the collision and take half its cargo).

Present but DISABLED by default after measuring negative or neutral value
against bot2 (constants gate them):

  * Control field (CONTROL_*_WEIGHT = 0): blurred influence map biasing
    mining and movement toward dominated territory.
  * Farming (FARM_START_STEP = 99999): leave cells near our yards to
    regenerate toward the 500 cap, harvest late. Lost hard vs a hunting
    opponent: it pushes miners on long trips through pirate territory.
  * Rate-based mining (SIT_LENGTHS unused): halite-per-turn trip scoring
    over-favored distant rich cells; bot2's distance-discounted halite
    keeps trips short and exposure low.
  * Interception hunting (reverted to chase-the-cell): aiming at the
    prey's escape square did not measurably beat naive chasing.

Safety core retained from bot2: reserved next-turn cells, no spawning onto
occupied yards, hard collision danger checks, endgame recall.

Run locally:
    uv run --script run-viewer.py bot4.py bot2.py random random
"""

from kaggle_environments.envs.halite.helpers import (
    Board,
    Point,
    ShipAction,
    ShipyardAction,
)

# --- Tunable strategy parameters --------------------------------------------
SPAWN_STOP_STEPS_LEFT = 70     # a new ship can't pay back 500 after this
FLEET_CAP_EARLY = 25           # cap while steps_left > 200
FLEET_CAP_MID = 18             # cap while steps_left > 120
CARGO_RETURN_THRESHOLD = 500   # cargo at which a ship heads home
LATE_RETURN_THRESHOLD = 200    # lower bar once steps_left < 100
TOPUP_DIST = 2                 # deposit opportunistically when this close
TOPUP_CARGO = 300              # ...and carrying at least this much
TARGET_MIN_HALITE = 20         # cells below this aren't mining targets
RETURN_LEG_WEIGHT = 0.4        # weight of the deposit leg in trip length
SIT_LENGTHS = (1, 2, 3, 4, 6, 8)   # candidate turns to sit mining a cell
CONTROL_RADIUS = 4             # influence blur radius
CONTROL_MINE_WEIGHT = 0.0     # how strongly control scales mining scores
CONTROL_MOVE_WEIGHT = 0.0      # how strongly control scores movement
FARM_RADIUS = 2                # plantation ring around our yards
FARM_HARVEST_HALITE = 470      # mine plantation cells this full (cap is 500)
FARM_STOP_STEPS_LEFT = 70      # strip the plantations near game end
FARM_START_STEP = 99999           # no farming before the economy is running
HUNT_MIN_PREY_CARGO = 100      # only chase enemies worth robbing
HUNT_WEIGHT = 0.7             # hunting score multiplier vs mining rates
HUNTERS_PER_PREY = 2           # pack size allowed on one target
HUNTER_FLEET_FRACTION = 1      # at most fleet/this many ships hunting
KILL_BONUS_CAP = 3            # movement bonus cap for stepping onto prey
ENDGAME_CONVERT_CARGO = 650    # bank-by-converting threshold (cost is 500)
DOCK_SEARCH_RADIUS = 4         # first-yard site search distance
DOCK_EVAL_RADIUS = 4           # neighborhood scored around dock candidates
DOCK_DIST_PENALTY = 150        # halite-equivalent cost per step walked
CONVERT_DEADLINE = 8           # convert in place if yard-less by this step
EXPAND_FLEET = 10              # fleet size that justifies another yard
EXPAND_MIN_DIST = 6            # new yard must be this far from existing ones
EXPAND_STOP_STEPS_LEFT = 120   # too late for a new yard to pay off
MAX_YARDS = 3
ENDGAME_MARGIN = 4             # slack turns when recalling cargo
DANGER_PENALTY = 1000          # movement penalty for entering a kill zone

_dock_target = None  # persists across turns within one episode

ALL_DIRECTIONS = [ShipAction.NORTH, ShipAction.EAST, ShipAction.SOUTH, ShipAction.WEST]
MINE_FRACTION = [1 - 0.75 ** t for t in range(max(SIT_LENGTHS) + 1)]


def toroidal_distance(a, b, size):
    dx = min((a.x - b.x) % size, (b.x - a.x) % size)
    dy = min((a.y - b.y) % size, (b.y - a.y) % size)
    return dx + dy


def cells_within(center, radius, size):
    for dy in range(-radius, radius + 1):
        remaining = radius - abs(dy)
        for dx in range(-remaining, remaining + 1):
            yield Point((center.x + dx) % size, (center.y + dy) % size), abs(dx) + abs(dy)


def find_dock_site(position, board, size):
    best_pos, best_score = position, None
    for pos, dist in cells_within(position, DOCK_SEARCH_RADIUS, size):
        neighborhood = sum(
            board.cells[p].halite
            for p, d in cells_within(pos, DOCK_EVAL_RADIUS, size)
            if d > 0
        )
        score = neighborhood - DOCK_DIST_PENALTY * dist
        if best_score is None or score > best_score:
            best_pos, best_score = pos, score
    return best_pos


def agent(obs, config):
    global _dock_target

    board = Board(obs, config)
    me = board.current_player
    size = board.configuration.size
    spawn_cost = board.configuration.spawn_cost
    convert_cost = board.configuration.convert_cost
    steps_left = board.configuration.episode_steps - board.step - 1

    halite_left = me.halite

    enemy_ships = [
        (s.position, s.halite, s.player_id)
        for p in board.opponents
        for s in p.ships
    ]
    enemy_yards = {sy.position for p in board.opponents for sy in p.shipyards}
    enemy_yards_by_player = {}
    for p in board.opponents:
        enemy_yards_by_player[p.id] = [sy.position for sy in p.shipyards]
    enemy_ship_at = {ep: ec for ep, ec, _ in enemy_ships}

    def dangerous(pos, cargo):
        return any(
            ec <= cargo and toroidal_distance(ep, pos, size) <= 1
            for ep, ec, _ in enemy_ships
        )

    # Control field: friendly presence minus enemy presence, blurred so a
    # ship 1 step away counts more than one 4 steps away.
    control = {}
    for ship in me.ships:
        for pos, d in cells_within(ship.position, CONTROL_RADIUS, size):
            control[pos] = control.get(pos, 0.0) + (CONTROL_RADIUS - d) / CONTROL_RADIUS
    for ep, _, _ in enemy_ships:
        for pos, d in cells_within(ep, CONTROL_RADIUS, size):
            control[pos] = control.get(pos, 0.0) - (CONTROL_RADIUS - d) / CONTROL_RADIUS

    # ---- Shipyard creation (same phased logic as bot2) ----------------------
    converting = set()
    if not me.shipyards and me.ships:
        pioneer = max(me.ships, key=lambda s: s.halite)
        if _dock_target is None:
            _dock_target = find_dock_site(pioneer.position, board, size)
        arrived = pioneer.position == _dock_target
        overdue = board.step >= CONVERT_DEADLINE
        if (arrived or overdue) and halite_left + pioneer.halite >= convert_cost:
            pioneer.next_action = ShipAction.CONVERT
            converting.add(pioneer.id)
            halite_left -= max(0, convert_cost - pioneer.halite)
            _dock_target = None
    elif (
        len(me.shipyards) < MAX_YARDS
        and len(me.ships) >= EXPAND_FLEET * len(me.shipyards)
        and steps_left > EXPAND_STOP_STEPS_LEFT
        and halite_left >= convert_cost + spawn_cost
    ):
        yard_pos = [sy.position for sy in me.shipyards]
        best_ship, best_score = None, None
        for ship in me.ships:
            if min(toroidal_distance(ship.position, y, size) for y in yard_pos) < EXPAND_MIN_DIST:
                continue
            neighborhood = sum(
                board.cells[p].halite
                for p, d in cells_within(ship.position, 3, size)
                if d > 0
            )
            if best_score is None or neighborhood > best_score:
                best_ship, best_score = ship, neighborhood
        if best_ship is not None:
            best_ship.next_action = ShipAction.CONVERT
            converting.add(best_ship.id)
            halite_left -= max(0, convert_cost - best_ship.halite)

    yard_positions = [sy.position for sy in me.shipyards]

    def nearest_yard_dist(pos):
        if not yard_positions:
            return None, 0
        best = min(yard_positions, key=lambda p: toroidal_distance(pos, p, size))
        return best, toroidal_distance(pos, best, size)

    # ---- Forced tasks: banking runs and endgame converts --------------------
    return_threshold = (
        CARGO_RETURN_THRESHOLD if steps_left > 100 else LATE_RETURN_THRESHOLD
    )
    targets = {}
    free_ships = []
    for ship in me.ships:
        if ship.id in converting:
            continue
        home, dist_home = nearest_yard_dist(ship.position)
        # Cargo that can no longer be sailed home is banked by converting:
        # conversion deposits instantly, netting cargo minus the 500 cost.
        stranded = home is None or steps_left < dist_home
        if (
            ship.halite >= ENDGAME_CONVERT_CARGO
            and (stranded or steps_left <= 2)
            and board.cells[ship.position].shipyard is None
        ):
            ship.next_action = ShipAction.CONVERT
            converting.add(ship.id)
            continue
        must_bank = home is not None and ship.halite > 0 and (
            ship.halite >= return_threshold
            or (ship.halite >= TOPUP_CARGO and dist_home <= TOPUP_DIST)
            or steps_left <= dist_home + ENDGAME_MARGIN
        )
        if must_bank:
            targets[ship.id] = home
        else:
            free_ships.append(ship)

    # ---- Mining candidates (with plantations set aside) ---------------------
    farming = (
        steps_left > FARM_STOP_STEPS_LEFT and board.step > FARM_START_STEP
    )
    mine_cells = []
    for pos, cell in board.cells.items():
        if cell.halite < TARGET_MIN_HALITE or pos in enemy_yards:
            continue
        _, d_home = nearest_yard_dist(pos)
        if (
            farming
            and yard_positions
            and d_home <= FARM_RADIUS
            and cell.halite < FARM_HARVEST_HALITE
        ):
            continue  # plantation: let it regenerate toward the cap
        mine_cells.append((pos, cell.halite, d_home))

    # ---- Global target auction ---------------------------------------------
    prey = []
    for ep, ec, epid in enemy_ships:
        if ec < HUNT_MIN_PREY_CARGO:
            continue
        # Aim at the escape square: the prey's neighbor closest to its own
        # nearest yard. Cornering its retreat beats tailing it.
        intercept = ep  # hunt like bot2: chase the prey's cell
        prey.append((ep, ec, intercept))

    bids = []
    for ship in free_ships:
        pos, cargo = ship.position, ship.halite
        for cell_pos, halite, d_home in mine_cells:
            if dangerous(cell_pos, cargo):
                continue
            d1 = toroidal_distance(pos, cell_pos, size)
            score = halite / (1 + d1 + RETURN_LEG_WEIGHT * d_home)
            bids.append((score, ship.id, ("mine", cell_pos)))
        if cargo == 0:
            for ep, ec, intercept in prey:
                d = toroidal_distance(pos, intercept, size)
                bids.append(
                    (HUNT_WEIGHT * ec / (1 + d), ship.id, ("hunt", ep, intercept))
                )

    bids.sort(key=lambda b: -b[0])
    taken_cells = set()
    hunter_counts = {}
    max_hunters = max(1, len(me.ships) // HUNTER_FLEET_FRACTION)
    total_hunters = 0
    for score, ship_id, task in bids:
        if ship_id in targets:
            continue
        if task[0] == "mine":
            if task[1] in taken_cells:
                continue
            taken_cells.add(task[1])
            targets[ship_id] = task[1]
        else:
            _, prey_pos, intercept = task
            if total_hunters >= max_hunters:
                continue
            n = hunter_counts.get(prey_pos, 0)
            if n >= HUNTERS_PER_PREY:
                continue
            hunter_counts[prey_pos] = n + 1
            total_hunters += 1
            # First hunter takes the escape square, the second tails the prey.
            targets[ship_id] = intercept if n == 0 else prey_pos

    # ---- Movement resolution ------------------------------------------------
    reserved = set()
    for ship in sorted(me.ships, key=lambda s: -s.halite):
        if ship.id in converting:
            continue
        pos, cargo = ship.position, ship.halite
        target = targets.get(ship.id, pos)

        if target == pos and pos in yard_positions and cargo == 0:
            best_adj, best_h = None, -1
            for action in ALL_DIRECTIONS:
                nxt = pos.translate(action.to_point(), size)
                if nxt in reserved or nxt in enemy_yards or dangerous(nxt, cargo):
                    continue
                if board.cells[nxt].halite > best_h:
                    best_adj, best_h = nxt, board.cells[nxt].halite
            if best_adj is not None:
                target = best_adj

        best_action, best_score, chosen = None, None, None
        for action in [None] + ALL_DIRECTIONS:
            nxt = pos if action is None else pos.translate(action.to_point(), size)
            if nxt in enemy_yards or nxt in reserved:
                continue
            score = -toroidal_distance(nxt, target, size)
            score += CONTROL_MOVE_WEIGHT * max(
                -2.0, min(2.0, control.get(nxt, 0.0))
            )
            victim = enemy_ship_at.get(nxt)
            if victim is not None and victim > cargo:
                score += min(victim / 50, KILL_BONUS_CAP)
            if dangerous(nxt, cargo):
                score -= DANGER_PENALTY
            if best_score is None or score > best_score:
                best_action, best_score, chosen = action, score, nxt
        if chosen is None:
            chosen = pos

        boxed_in = best_score is not None and best_score <= -DANGER_PENALTY + KILL_BONUS_CAP
        if (
            boxed_in
            and cargo >= convert_cost + 100
            and board.cells[pos].shipyard is None
        ):
            ship.next_action = ShipAction.CONVERT
            continue

        ship.next_action = best_action
        reserved.add(chosen)

    # ---- Spawning -----------------------------------------------------------
    if steps_left > 200:
        fleet_cap = FLEET_CAP_EARLY
    elif steps_left > 120:
        fleet_cap = FLEET_CAP_MID
    else:
        fleet_cap = 0
    fleet_size = len(me.ships)
    if fleet_size == 0 and steps_left > 30:
        fleet_cap = max(fleet_cap, 1)

    threat_near_yard = {
        sy.position
        for sy in me.shipyards
        if any(
            toroidal_distance(ep, sy.position, size) <= 2 for ep, _, _ in enemy_ships
        )
    }
    for shipyard in me.shipyards:
        if halite_left < spawn_cost or shipyard.position in reserved:
            continue
        under_cap = fleet_size < fleet_cap and steps_left > SPAWN_STOP_STEPS_LEFT
        if under_cap or shipyard.position in threat_near_yard:
            shipyard.next_action = ShipyardAction.SPAWN
            reserved.add(shipyard.position)
            halite_left -= spawn_cost
            fleet_size += 1

    return me.next_actions
