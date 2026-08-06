"""Halite tournament bot, second generation.

Architectural differences from bot.py:

  * Global task assignment: every (ship, target) pair is scored into one
    matrix -- mining cells, hunting laden enemy ships -- and assignments are
    taken best-first across the whole fleet, so early ships no longer steal
    the good cells from later ones.
  * Aggressive spawn economics: a ship is an investment that pays back over
    the remaining turns, so the fleet cap is high early and shrinks as the
    payback window closes.
  * Hunting packs: empty ships are allowed to chase laden enemy ships
    (lighter ship wins the collision and steals half the cargo); up to two
    hunters per prey so retreats get cut off.
  * Expansion: a second and third shipyard once the fleet outgrows one,
    placed under a ship that is already far from home in a rich area.
  * Same safety core that fixed the old bots: reserved next-turn cells,
    no spawning onto occupied yards, threat-aware movement, endgame recall.

Run locally:
    uv run --script run-viewer.py colton.py bot.py random random
"""

from kaggle_environments.envs.halite.helpers import (
    Board,
    Point,
    ShipAction,
    ShipyardAction,
)

# --- Tunable strategy parameters (Optimized for 5000 Starting Halite) --------
SPAWN_STOP_STEPS_LEFT = 60     # Ships pay back faster on rich regenerating maps
FLEET_CAP_EARLY = 40           # Aggressive expansion with 5k starting bank
FLEET_CAP_MID = 25             # Scale down mid-game as map density drops
CARGO_RETURN_THRESHOLD = 600   # Higher cargo threshold to maximize trip efficiency
LATE_RETURN_THRESHOLD = 150    # Low bar near end-game to guarantee deposit
TOPUP_DIST = 2                 # Opportunistic deposit distance
TOPUP_CARGO = 300              # Opportunistic deposit cargo amount

TARGET_MIN_HALITE = 25         # Avoid stripping regenerating tiles down to 0
HOME_DIST_WEIGHT = 0.35        # Discount distant cells slightly less early on

HUNT_MIN_PREY_CARGO = 50       # Aggressive hunting (smallest ship steals cargo)
HUNT_WEIGHT = 1.0              # Equal priority to hunting laden enemies vs mining
HUNTERS_PER_PREY = 2           # Pack size to cut off retreats

DOCK_SEARCH_RADIUS = 5         # Search radius for initial shipyard placement
DOCK_EVAL_RADIUS = 4           # Neighborhood evaluation radius
DOCK_DIST_PENALTY = 100        # Walking cost penalty
CONVERT_DEADLINE = 5           # Convert faster on step 1 with plentiful funds

EXPAND_FLEET = 12              # Build 2nd/3rd shipyard every 12 ships
EXPAND_MIN_DIST = 7            # Keep shipyards spread across the map
EXPAND_STOP_STEPS_LEFT = 100   # Stop building yards late in the game
MAX_YARDS = 3                  # Cap total shipyards

ENDGAME_MARGIN = 3             # Extra turn buffer when recalling ships at step 400
DANGER_PENALTY = 1000          # Penalty for entering a kill zone

_dock_target = None  # persists across turns within one episode

ALL_DIRECTIONS = [ShipAction.NORTH, ShipAction.EAST, ShipAction.SOUTH, ShipAction.WEST]


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
    """Richest close-by neighborhood; walking costs halite-equivalent turns."""
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

    enemy_ships = [(s.position, s.halite) for p in board.opponents for s in p.ships]
    enemy_yards = {sy.position for p in board.opponents for sy in p.shipyards}

    def dangerous(pos, cargo):
        return any(
            ec <= cargo and toroidal_distance(ep, pos, size) <= 1
            for ep, ec in enemy_ships
        )

    # ---- Shipyard creation --------------------------------------------------
    converting = set()

    if not me.shipyards and me.ships:
        # No yard at all: rebuild under the richest ship (its cargo offsets
        # the cost and deposits instantly), walking to a dock site at game
        # start when there is time to be picky.
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
        # Expansion: convert a ship that is already far from every yard and
        # sitting in the richest neighborhood among the candidates.
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

    def nearest_yard(pos):
        return min(
            yard_positions,
            key=lambda p: toroidal_distance(pos, p, size),
            default=None,
        )

    # ---- Task assignment ----------------------------------------------------
    # Ships that must bank cargo are forced home; everyone else enters a
    # global (ship, target) auction over mining cells and hunting targets.
    return_threshold = (
        CARGO_RETURN_THRESHOLD if steps_left > 100 else LATE_RETURN_THRESHOLD
    )
    targets = {}       # ship.id -> Point to head for
    free_ships = []

    for ship in me.ships:
        if ship.id in converting:
            continue
        home = nearest_yard(ship.position)
        dist_home = (
            toroidal_distance(ship.position, home, size) if home is not None else 0
        )
        must_bank = home is not None and ship.halite > 0 and (
            ship.halite >= return_threshold
            or (ship.halite >= TOPUP_CARGO and dist_home <= TOPUP_DIST)
            or steps_left <= dist_home + ENDGAME_MARGIN
        )
        if must_bank:
            targets[ship.id] = home
        else:
            free_ships.append(ship)

    # Candidate targets: worthwhile cells anywhere on the board, plus laden
    # enemy ships for empty hunters.
    mine_cells = [
        (pos, cell.halite)
        for pos, cell in board.cells.items()
        if cell.halite >= TARGET_MIN_HALITE and pos not in enemy_yards
    ]
    prey = [(ep, ec) for ep, ec in enemy_ships if ec >= HUNT_MIN_PREY_CARGO]

    bids = []
    for ship in free_ships:
        pos, cargo = ship.position, ship.halite
        for cell_pos, halite in mine_cells:
            if dangerous(cell_pos, cargo):
                continue
            d = toroidal_distance(pos, cell_pos, size)
            home = nearest_yard(cell_pos)
            d_home = toroidal_distance(cell_pos, home, size) if home else 0
            score = halite / (1 + d + HOME_DIST_WEIGHT * d_home)
            bids.append((score, ship.id, ("mine", cell_pos)))
        if cargo == 0:
            for prey_pos, prey_cargo in prey:
                d = toroidal_distance(pos, prey_pos, size)
                score = HUNT_WEIGHT * prey_cargo / (1 + d)
                bids.append((score, ship.id, ("hunt", prey_pos)))

    bids.sort(key=lambda b: -b[0])
    taken_cells = set()
    hunter_counts = {}
    for score, ship_id, (kind, tpos) in bids:
        if ship_id in targets:
            continue
        if kind == "mine":
            if tpos in taken_cells:
                continue
            taken_cells.add(tpos)
        else:
            if hunter_counts.get(tpos, 0) >= HUNTERS_PER_PREY:
                continue
            hunter_counts[tpos] = hunter_counts.get(tpos, 0) + 1
        targets[ship_id] = tpos

    # ---- Movement resolution ------------------------------------------------
    reserved = set()
    for ship in sorted(me.ships, key=lambda s: -s.halite):
        if ship.id in converting:
            continue
        pos, cargo = ship.position, ship.halite
        target = targets.get(ship.id, pos)

        # An empty ship parked on its own yard blocks spawning: step off.
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
            if dangerous(nxt, cargo):
                score -= DANGER_PENALTY
            if best_score is None or score > best_score:
                best_action, best_score, chosen = action, score, nxt
        if chosen is None:
            chosen = pos  # boxed in by our own fleet: hold

        # Cornered with a fat cargo: convert, banking it before collision.
        boxed_in = best_score is not None and best_score <= -DANGER_PENALTY
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
        if any(toroidal_distance(ep, sy.position, size) <= 2 for ep, _ in enemy_ships)
    }
    for shipyard in me.shipyards:
        if halite_left < spawn_cost or shipyard.position in reserved:
            continue
        under_cap = fleet_size < fleet_cap and steps_left > SPAWN_STOP_STEPS_LEFT
        # A spawned ship also bodyguards the yard against adjacent raiders.
        if under_cap or shipyard.position in threat_near_yard:
            shipyard.next_action = ShipyardAction.SPAWN
            reserved.add(shipyard.position)
            halite_left -= spawn_cost
            fleet_size += 1

    return me.next_actions