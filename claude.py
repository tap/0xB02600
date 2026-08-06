"""
Halite 4 Agent with Fixed Shipyard Creation & Integrated Collision Avoidance
"""

from kaggle_environments.envs.halite.helpers import Board, Point, ShipAction, ShipyardAction

# --- Strategy Parameters ---------------------------------------------------
CARGO_RETURN_THRESHOLD = 500  # Cargo at which a ship heads home
MINE_MIN_HALITE = 50          # Minimum halite on tile to stay and mine
MAX_SHIPS = 20                 # Ship cap
SPAWN_UNTIL_STEP = 300        # Stop spawning after this step
DOCK_SEARCH_RADIUS = 7        # Scout radius for shipyard placement
DOCK_EVAL_RADIUS = 5          # Area evaluation radius for shipyard placement
MINE_SEARCH_RADIUS = 5        # Search radius for target halite tiles

_dock_target = None


# --- Board & Navigation Helpers ---------------------------------------------

def get_destination(origin: Point, action: ShipAction, size: int) -> Point:
    """Calculates the target Point resulting from an action on a toroidal board."""
    if action is None:
        return origin
    if action == ShipAction.NORTH:
        return Point(origin.x, (origin.y + 1) % size)
    if action == ShipAction.SOUTH:
        return Point(origin.x, (origin.y - 1) % size)
    if action == ShipAction.EAST:
        return Point((origin.x + 1) % size, origin.y)
    if action == ShipAction.WEST:
        return Point((origin.x - 1) % size, origin.y)
    return origin


def get_directional_actions(origin: Point, target: Point, size: int):
    """
    Returns candidate ShipActions ordered by preference for moving toward `target`.
    Includes `None` (STAY) at the end as a safe baseline fallback.
    """
    if origin == target:
        return [None]

    dx_east = (target.x - origin.x) % size
    dx_west = (origin.x - target.x) % size
    dy_north = (target.y - origin.y) % size
    dy_south = (origin.y - target.y) % size

    primary_x = ShipAction.EAST if dx_east <= dx_west else ShipAction.WEST
    dist_x = min(dx_east, dx_west)

    primary_y = ShipAction.NORTH if dy_north <= dy_south else ShipAction.SOUTH
    dist_y = min(dy_north, dy_south)

    actions = []
    # Prioritize moving along the axis with the larger distance
    if dist_x >= dist_y:
        if dist_x > 0: actions.append(primary_x)
        if dist_y > 0: actions.append(primary_y)
    else:
        if dist_y > 0: actions.append(primary_y)
        if dist_x > 0: actions.append(primary_x)

    # Append remaining orthogonal movements as low-priority alternatives
    all_moves = [ShipAction.NORTH, ShipAction.SOUTH, ShipAction.EAST, ShipAction.WEST]
    for move in all_moves:
        if move not in actions:
            actions.append(move)

    actions.append(None)  # Holding position
    return actions


def is_enemy_threat(target_pos: Point, ship, board) -> bool:
    """
    Checks if moving to target_pos risks a collision with an enemy ship that
    has equal or less cargo (which would destroy or tie our ship).
    """
    cell = board.cells[target_pos]
    if cell.ship is not None and cell.ship.player_id != ship.player_id:
        if cell.ship.halite <= ship.halite:
            return True

    # Check neighboring cells for hostile ships that could step into target_pos
    for neighbor in [cell.north, cell.south, cell.east, cell.west]:
        if neighbor.ship is not None and neighbor.ship.player_id != ship.player_id:
            if neighbor.ship.halite <= ship.halite:
                return True

    return False


def toroidal_distance(a: Point, b: Point, size: int) -> int:
    dx = min((a.x - b.x) % size, (b.x - a.x) % size)
    dy = min((a.y - b.y) % size, (b.y - a.y) % size)
    return dx + dy


def neighborhood_halite(board, center: Point, size: int, eval_radius: int) -> int:
    total = 0
    for dy in range(-eval_radius, eval_radius + 1):
        remaining = eval_radius - abs(dy)
        for dx in range(-remaining, remaining + 1):
            if dx == 0 and dy == 0:
                continue
            x = (center.x + dx) % size
            y = (center.y + dy) % size
            total += board.cells[Point(x, y)].halite
    return total


def find_best_dock_site(ship, board, search_radius=DOCK_SEARCH_RADIUS, eval_radius=DOCK_EVAL_RADIUS):
    size = board.configuration.size
    start = ship.position
    best_pos = start
    best_total = neighborhood_halite(board, start, size, eval_radius)
    best_distance = 0

    for dy in range(-search_radius, search_radius + 1):
        remaining = search_radius - abs(dy)
        for dx in range(-remaining, remaining + 1):
            if dx == 0 and dy == 0:
                continue
            pos = Point((start.x + dx) % size, (start.y + dy) % size)
            distance = abs(dx) + abs(dy)
            total = neighborhood_halite(board, pos, size, eval_radius)

            if total > best_total or (total == best_total and distance < best_distance):
                best_pos, best_total, best_distance = pos, total, distance

    return best_pos


def find_richest_cell(board, start: Point, radius: int):
    size = board.configuration.size
    best_pos = start
    best_amount = board.cells[start].halite
    best_distance = 0

    for dy in range(-radius, radius + 1):
        remaining = radius - abs(dy)
        for dx in range(-remaining, remaining + 1):
            pos = Point((start.x + dx) % size, (start.y + dy) % size)
            distance = abs(dx) + abs(dy)
            amount = board.cells[pos].halite

            if amount > best_amount or (amount == best_amount and distance < best_distance):
                best_pos, best_amount, best_distance = pos, amount, distance

    return best_pos, best_amount

def agent(obs, config):
    global _dock_target

    board = Board(obs, config)
    me = board.current_player
    size = board.configuration.size
    convert_cost = board.configuration.convert_cost
    spawn_cost = board.configuration.spawn_cost

    available_halite = me.halite
    shipyard_positions = [sy.position for sy in me.shipyards]

    # Track cells reserved for the upcoming turn to prevent collisions
    occupied_positions = set()
    unassigned_ships = list(me.ships)

    # ------------------------------------------------------------------------
    # STEP 1: Handle Initial Shipyard Construction (Starter Docking)
    # ------------------------------------------------------------------------
    if not me.shipyards and unassigned_ships:
        starter = unassigned_ships[0]

        if _dock_target is None:
            _dock_target = find_best_dock_site(starter, board)

        if starter.position == _dock_target:
            if available_halite >= convert_cost:
                starter.next_action = ShipAction.CONVERT
                available_halite -= convert_cost
                _dock_target = None
                occupied_positions.add(starter.position)
                unassigned_ships.remove(starter)
        else:
            # Force the starter ship to route specifically to _dock_target
            preferred_actions = get_directional_actions(starter.position, _dock_target, size)
            for action in preferred_actions:
                dest = get_destination(starter.position, action, size)
                if dest not in occupied_positions:
                    starter.next_action = action
                    occupied_positions.add(dest)
                    unassigned_ships.remove(starter)
                    break

    # ------------------------------------------------------------------------
    # STEP 2: Shipyard Spawning & Dock Reservations
    # ------------------------------------------------------------------------
    if board.step < SPAWN_UNTIL_STEP:
        projected_ships = len(me.ships)
        for shipyard in me.shipyards:
            if projected_ships >= MAX_SHIPS:
                break
            # Spawn if we have enough halite
            if available_halite >= spawn_cost:
                shipyard.next_action = ShipyardAction.SPAWN
                available_halite -= spawn_cost
                projected_ships += 1
                # Reserve shipyard cell so returning ships don't collide with the newly spawned ship
                occupied_positions.add(shipyard.position)

    # ------------------------------------------------------------------------
    # STEP 3: Identify Target Goals for Each Remaining Unassigned Ship
    # ------------------------------------------------------------------------
    ship_intentions = []  # List of tuples: (ship, target_pos, is_mining)

    for ship in unassigned_ships:
        if ship.next_action is not None:
            continue

        # Case A: High cargo -> return home
        if shipyard_positions and ship.halite >= CARGO_RETURN_THRESHOLD:
            nearest = min(shipyard_positions, key=lambda p: toroidal_distance(ship.position, p, size))
            ship_intentions.append((ship, nearest, False))

        # Case B: Stationary mining on current cell
        elif ship.cell.halite >= MINE_MIN_HALITE:
            ship_intentions.append((ship, ship.position, True))

        # Case C: Seek richer halite cell
        else:
            target, amount = find_richest_cell(board, ship.position, MINE_SEARCH_RADIUS)
            if target == ship.position or amount < MINE_MIN_HALITE:
                ship_intentions.append((ship, ship.position, True))
            else:
                ship_intentions.append((ship, target, False))

    # Sort ships by priority:
    # 1. Stationary miners first (reserving their tile)
    # 2. Ships carrying higher cargo next
    ship_intentions.sort(key=lambda item: (not item[2], -item[0].halite))

    # ------------------------------------------------------------------------
    # STEP 4: Resolve Movement and Reserve Tiles
    # ------------------------------------------------------------------------
    for ship, target_pos, is_mining in ship_intentions:
        if is_mining and ship.position not in occupied_positions:
            # Mining in place is safe; claim the current tile
            ship.next_action = None
            occupied_positions.add(ship.position)
            continue

        # Find preferred directional actions toward the intended target
        preferred_actions = get_directional_actions(ship.position, target_pos, size)
        chosen_action = None

        for action in preferred_actions:
            dest = get_destination(ship.position, action, size)

            # Accept action if target tile is unoccupied and safe from hostile rams
            if dest not in occupied_positions and not is_enemy_threat(dest, ship, board):
                chosen_action = action
                occupied_positions.add(dest)
                break

        # Emergency Fallback: If all preferred directions are blocked or dangerous
        if chosen_action is None and ship.next_action is None:
            for fallback_action in [ShipAction.NORTH, ShipAction.SOUTH, ShipAction.EAST, ShipAction.WEST, None]:
                dest = get_destination(ship.position, fallback_action, size)
                if dest not in occupied_positions:
                    chosen_action = fallback_action
                    occupied_positions.add(dest)
                    break

        ship.next_action = chosen_action

    return me.next_actions