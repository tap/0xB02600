"""Halite tournament bot, second generation.

Architectural differences from bot.py:

  * Global task assignment: every (ship, target) pair is scored into one
    matrix -- mining cells, hunting laden enemy ships -- and assignments are
    taken best-first across the whole fleet, so early ships no longer steal
    the good cells from later ones[cite: 3].
  * Aggressive spawn economics: a ship is an investment that pays back over
    the remaining turns, so the fleet cap is high early and shrinks as the
    payback window closes[cite: 3].
  * Hunting packs: empty ships are allowed to chase laden enemy ships
    (lighter ship wins the collision and steals half the cargo); up to two
    hunters per prey so retreats get cut off[cite: 3].
  * Expansion: a second and third shipyard once the fleet outgrows one,
    placed under a ship that is already far from home in a rich area[cite: 3].
  * Same safety core that fixed the old bots: reserved next-turn cells,
    no spawning onto occupied yards, threat-aware movement, endgame recall[cite: 3].

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
FLEET_CAP_EARLY = 25           # Controlled early fleet size to prevent overcrowding
FLEET_CAP_MID = 18             # Scale down mid-game as map density drops
CARGO_RETURN_THRESHOLD = 500   # Solid return threshold to maximize trip efficiency
LATE_RETURN_THRESHOLD = 150    # Low bar near end-game to guarantee deposit
TOPUP_DIST = 2                 # Opportunistic deposit distance[cite: 3]
TOPUP_CARGO = 300              # Opportunistic deposit cargo amount[cite: 3]

HOME_DIST_WEIGHT = 0.35        # Discount distant cells slightly less early on[cite: 3]
CLUSTER_WEIGHT = 0.10          # Weight applied to surrounding cluster density

HUNT_MIN_PREY_CARGO = 250      # Only hunt enemies loaded with fat cargo
HUNT_WEIGHT = 0.35             # Balanced priority between hunting vs mining
HUNTERS_PER_PREY = 2           # Pack size to cut off retreats[cite: 3]

DOCK_SEARCH_RADIUS = 5         # Search radius for initial shipyard placement[cite: 3]
DOCK_EVAL_RADIUS = 4           # Neighborhood evaluation radius[cite: 3]
DOCK_DIST_PENALTY = 100        # Walking cost penalty[cite: 3]
CONVERT_DEADLINE = 5           # Convert faster on step 1 with plentiful funds[cite: 3]

EXPAND_FLEET = 10              # Build 2nd shipyard at 10 ships, 3rd at 20
EXPAND_MIN_DIST = 8            # Keep shipyards spread across the map
EXPAND_STOP_STEPS_LEFT = 110   # Stop building yards late in the game
MAX_YARDS = 3                  # Cap total shipyards

ENDGAME_MARGIN = 4             # Extra turn buffer when recalling ships at step 400
DANGER_PENALTY = 1000          # Penalty for entering a kill zone[cite: 3]

_dock_target = None  # persists across turns within one episode[cite: 3]

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


def get_min_halite_threshold(steps_left):
    """Dynamically scales mining floor to protect 2% turn compounding early."""
    if steps_left > 250:
        return 60  # Leave buffer to preserve map regeneration rate
    elif steps_left > 100:
        return 25  # Standard mid-game threshold
    else:
        return 0   # Strip everything clean before end of match


def get_neighborhood_value(board, center_pos, radius=2):
    """Calculates surrounding density so ships favor rich clusters over isolated tiles."""
    total = 0
    size = board.configuration.size
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            pos = Point((center_pos.x + dx) % size, (center_pos.y + dy) % size)
            total += board.cells[pos].halite
    return total


def classify_collision(friendly_cargo, enemy_cargo):
    """
    Returns collision outcome from friendly ship perspective:
    1: Win (Friendly survives, steals 50% cargo)
    0: Mutual Destruction (Both die)
    -1: Loss (Friendly destroyed)
    """
    if friendly_cargo < enemy_cargo:
        return 1
    elif friendly_cargo == enemy_cargo:
        return 0
    else:
        return -1


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
        """Checks if stepping into pos risks losing a collision against an enemy."""
        cell = board.cells[pos]
        if cell.ship is not None and cell.ship.player_id != me.id:
            if classify_collision(cargo, cell.ship.halite) <= 0:
                return True
        for neighbor in [cell.north, cell.south, cell.east, cell.west]:
            if neighbor.ship is not None and neighbor.ship.player_id != me.id:
                if classify_collision(cargo, neighbor.ship.halite) <= 0:
                    return True
        return False

    converting = set()
    targets = {}  # ship.id -> Point to head for[cite: 3]

    # ---- Shipyard creation --------------------------------------------------
    if not me.shipyards and me.ships:
        starter = max(me.ships, key=lambda s: s.halite)
        if _dock_target is None:
            _dock_target = find_dock_site(starter.position, board, size)

        arrived = starter.position == _dock_target
        overdue = board.step >= CONVERT_DEADLINE

        if (arrived or overdue) and halite_left + starter.halite >= convert_cost:
            starter.next_action = ShipAction.CONVERT
            converting.add(starter.id)
            halite_left -= max(0, convert_cost - starter.halite)
            _dock_target = None
        else:
            targets[starter.id] = _dock_target

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
            neighborhood = get_neighborhood_value(board, ship.position, radius=3)
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
    return_threshold = (
        CARGO_RETURN_THRESHOLD if steps_left > 100 else LATE_RETURN_THRESHOLD
    )
    free_ships = []

    for ship in me.ships:
        if ship.id in converting or ship.id in targets:
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

    # Dynamic mining threshold & Candidate target generation
    min_halite_floor = get_min_halite_threshold(steps_left)
    mine_cells = [
        (pos, cell.halite)
        for pos, cell in board.cells.items()
        if cell.halite >= min_halite_floor and pos not in enemy_yards
    ]
    prey = [(ep, ec) for ep, ec in enemy_ships if ec >= HUNT_MIN_PREY_CARGO]

    bids = []
    for ship in free_ships:
        pos, cargo = ship.position, ship.halite

        # Score mining cells (incorporating cluster density)
        for cell_pos, halite in mine_cells:
            if dangerous(cell_pos, cargo):
                continue
            d = toroidal_distance(pos, cell_pos, size)
            home = nearest_yard(cell_pos)
            d_home = toroidal_distance(cell_pos, home, size) if home else 0
            cluster_density = get_neighborhood_value(board, cell_pos, radius=4)
            effective_halite = halite + (CLUSTER_WEIGHT * cluster_density)
            score = effective_halite / (1 + d + HOME_DIST_WEIGHT * d_home)
            bids.append((score, ship.id, ("mine", cell_pos)))

        # Score hunting targets (0-cargo ships targeting laden enemies)
        if cargo == 0:
            for prey_pos, prey_cargo in prey:
                d = toroidal_distance(pos, prey_pos, size)
                stolen_halite = prey_cargo * 0.50
                score = (HUNT_WEIGHT * stolen_halite) / (1 + d)
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

    # FALLBACK: Ensure every free ship gets assigned a target instead of idling
    all_positive_halite_cells = [pos for pos, cell in board.cells.items() if cell.halite > 0]
    for ship in free_ships:
        if ship.id not in targets:
            if all_positive_halite_cells:
                best_fallback = min(
                    all_positive_halite_cells,
                    key=lambda p: toroidal_distance(ship.position, p, size)
                )
                targets[ship.id] = best_fallback
            else:
                home = nearest_yard(ship.position)
                targets[ship.id] = home if home else ship.position

    # ---- Movement resolution ------------------------------------------------
    reserved = set()
    for ship in sorted(me.ships, key=lambda s: -s.halite):
        if ship.id in converting:
            continue
        pos, cargo = ship.position, ship.halite
        target = targets.get(ship.id, pos)

        # Force idle ships parked on/near yard to step off and make room
        if (pos in yard_positions or any(toroidal_distance(pos, y, size) <= 1 for y in yard_positions)) and target == pos:
            best_adj, best_h = None, -1
            for action in ALL_DIRECTIONS:
                nxt = pos.translate(action.to_point(), size)
                if nxt in reserved or nxt in enemy_yards:
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
            chosen = pos  # boxed in by our own fleet: hold[cite: 3]

        # Cornered with fat cargo: convert, banking it before collision[cite: 3].
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
        # A spawned ship bodyguards the yard against adjacent raiders[cite: 3].
        if under_cap or shipyard.position in threat_near_yard:
            shipyard.next_action = ShipyardAction.SPAWN
            reserved.add(shipyard.position)
            halite_left -= spawn_cost
            fleet_size += 1

    return me.next_actions