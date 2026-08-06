from kaggle_environments.envs.halite.helpers import *

# --- Tunable strategy parameters --------------------------------------------
CARGO_RETURN_THRESHOLD = 500  # Cargo at which a ship heads home to deposit
MINE_MIN_HALITE = 50          # Only bother mining a cell with at least this much
MAX_SHIPS = 8                 # Stop spawning once we have this many ships
SPAWN_UNTIL_STEP = 300        # Don't spawn new ships after this step

def toroidal_distance(a, b, size):
    """Manhattan distance on a wrap-around board."""
    dx = min((a.x - b.x) % size, (b.x - a.x) % size)
    dy = min((a.y - b.y) % size, (b.y - a.y) % size)
    return dx + dy

def move_towards(origin, target, size):
    """Return a single ShipAction stepping from origin toward target (or None)."""
    if origin == target:
        return None

    east = (target.x - origin.x) % size
    west = (origin.x - target.x) % size
    north = (target.y - origin.y) % size
    south = (origin.y - target.y) % size

    # Prioritize the axis where we are furthest away from the target
    if max(east, west) >= max(north, south):
        if east != 0 or west != 0:
            return ShipAction.EAST if east <= west else ShipAction.WEST
    else:
        if north != 0 or south != 0:
            return ShipAction.NORTH if north <= south else ShipAction.SOUTH

    return None

def agent(obs, config):
    board = Board(obs, config)
    me = board.current_player
    size = config.size

    # Track planned movements to prevent team collisions
    occupied_next_cells = set()

    # 1. Manage Shipyards (Spawning)
    shipyards = me.shipyards
    ships = me.ships

    # Spawn logic
    if len(shipyards) > 0:
        for shipyard in shipyards:
            if (len(ships) < MAX_SHIPS and
                board.step < SPAWN_UNTIL_STEP and
                me.halite >= 500 and
                shipyard.cell.position not in occupied_next_cells):

                shipyard.next_action = ShipyardAction.SPAWN
                occupied_next_cells.add(shipyard.cell.position)

    # 2. Manage Ships
    for i, ship in enumerate(ships):
        # Convert first ship to shipyard if we don't have one
        if len(shipyards) == 0 and i == 0:
            # Only convert if cargo is low so we don't destroy halite pockets
            if me.halite + ship.halite >= 500:
                ship.next_action = ShipAction.CONVERT
                continue

        # Strategy A: Return home if cargo is full
        if ship.halite >= CARGO_RETURN_THRESHOLD and len(shipyards) > 0:
            nearest_yard = min(shipyards, key=lambda y: toroidal_distance(ship.cell.position, y.cell.position, size))
            action = move_towards(ship.cell.position, nearest_yard.cell.position, size)

            if action:
                target_pos = ship.cell.neighbor(action.to_point()).position
                if target_pos not in occupied_next_cells:
                    ship.next_action = action
                    occupied_next_cells.add(target_pos)
                    continue

        # Strategy B: Mine current cell if it's rich enough
        if ship.cell.halite >= MINE_MIN_HALITE and ship.halite < CARGO_RETURN_THRESHOLD:
            # Staying still counts as occupying our current cell
            occupied_next_cells.add(ship.cell.position)
            continue

        # Strategy C: Seek richest local cell
        best_cell = ship.cell
        max_halite = ship.cell.halite

        # Check all 4 compass directions using the neighbor() method
        for direction in [ShipAction.NORTH, ShipAction.SOUTH, ShipAction.EAST, ShipAction.WEST]:
            neighbor = ship.cell.neighbor(direction.to_point())
            if neighbor.halite > max_halite:
                max_halite = neighbor.halite
                best_cell = neighbor

        if best_cell != ship.cell:
            action = move_towards(ship.cell.position, best_cell.position, size)
            if action:
                target_pos = ship.cell.neighbor(action.to_point()).position
                if target_pos not in occupied_next_cells:
                    ship.next_action = action
                    occupied_next_cells.add(target_pos)
                    continue

        # Default safety fallback: stay put
        occupied_next_cells.add(ship.cell.position)

    return me.next_actions
