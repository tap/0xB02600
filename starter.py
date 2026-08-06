"""Base Halite submission agent.

A minimal but complete starting point you can build on. It uses the Board
helper API from kaggle-environments and follows a simple strategy:

  * Convert the first ship into a shipyard if we don't have one yet.
  * Spawn new ships from a shipyard while we're under the ship cap.
  * Each ship mines the halite it's sitting on, heads home to deposit once
    its cargo is high, and otherwise moves toward the richest nearby cell.

Run it with the viewer, e.g.:
    uv run --script .\\run-viewer.py submissions\\starter.py random random random
"""

from kaggle_environments.envs.halite.helpers import *

# --- Tunable strategy parameters --------------------------------------------
CARGO_RETURN_THRESHOLD = 500  # cargo at which a ship heads home to deposit
MINE_MIN_HALITE = 50          # only bother mining a cell with at least this much
MAX_SHIPS = 8                 # stop spawning once we have this many ships
SPAWN_UNTIL_STEP = 300        # don't spawn new ships after this step
DOCK_SEARCH_RADIUS = 7          # how far the starter ship scouts for a dock site
DOCK_EVAL_RADIUS = 5            # how big a neighborhood to score around each candidate
_dock_target = None              # persists across turns within this episode


def toroidal_distance(a, b, size):
    """Manhattan distance on a wrap-around board."""
    dx = min((a.x - b.x) % size, (b.x - a.x) % size)
    dy = min((a.y - b.y) % size, (b.y - a.y) % size)
    return dx + dy


def neighborhood_halite(board, center, size, eval_radius):
    """
    Sum halite within `eval_radius` (Manhattan distance) of `center`,
    NOT counting `center` itself, since a shipyard sits on that cell
    and produces no halite once built there.
    """
    total = 0
    for dy in range(-eval_radius, eval_radius + 1):
        remaining = eval_radius - abs(dy)
        for dx in range(-remaining, remaining + 1):
            if dx == 0 and dy == 0:
                continue  # skip the candidate cell itself
            x = (center.x + dx) % size
            y = (center.y + dy) % size
            total += board.cells[Point(x, y)].halite
    return total


def find_best_dock_site(ship, board, search_radius=DOCK_SEARCH_RADIUS,
                         eval_radius=DOCK_EVAL_RADIUS):
    """
    Search the toroidal board within `search_radius` of the ship for the
    position whose surrounding `eval_radius` neighborhood holds the most
    total halite (excluding the candidate cell itself, since building a
    shipyard there wipes out that cell's halite). This favors a spot
    NEXT TO a rich patch over sitting directly on top of it, so the ship
    can keep mining the good tiles after converting.

    Ties in neighborhood total are broken by picking the candidate
    closer to the ship's current position.

    Returns the Point of the best candidate found.
    """
    size = board.configuration.size
    start = ship.position

    best_pos = start
    best_total = neighborhood_halite(board, start, size, eval_radius)
    best_distance = 0

    for dy in range(-search_radius, search_radius + 1):
        remaining = search_radius - abs(dy)
        for dx in range(-remaining, remaining + 1):
            if dx == 0 and dy == 0:
                continue  # already scored as the starting candidate above
            x = (start.x + dx) % size
            y = (start.y + dy) % size
            pos = Point(x, y)
            distance = abs(dx) + abs(dy)

            total = neighborhood_halite(board, pos, size, eval_radius)

            if total > best_total or (total == best_total and distance < best_distance):
                best_pos, best_total, best_distance = pos, total, distance

    return best_pos

def move_towards(origin, target, size):
    """Return a single ShipAction stepping from origin toward target (or None)."""
    if origin == target:
        return None
    east = (target.x - origin.x) % size
    west = (origin.x - target.x) % size
    north = (target.y - origin.y) % size
    south = (origin.y - target.y) % size
    # Move along whichever axis we're farther from, closing the shortest way.
    if east != 0 or west != 0:
        return ShipAction.EAST if east <= west else ShipAction.WEST
    if north != 0 or south != 0:
        return ShipAction.NORTH if north <= south else ShipAction.SOUTH
    return None


def best_neighbor_action(ship, board):
    """Move toward the adjacent cell with the most halite (or mine in place)."""
    cell = ship.cell
    # If the current cell is worth mining, stay put and collect.
    if cell.halite >= MINE_MIN_HALITE:
        return None
    options = {
        ShipAction.NORTH: cell.north.halite,
        ShipAction.EAST: cell.east.halite,
        ShipAction.SOUTH: cell.south.halite,
        ShipAction.WEST: cell.west.halite,
    }
    best_action = max(options, key=options.get)
    # If nothing nearby is worth it, just mine where we are.
    if options[best_action] < MINE_MIN_HALITE:
        return None
    return best_action

def find_richest_cell(board, start, radius):
    """
    Search the toroidal board for the single cell with the most halite
    within `radius` (Manhattan distance) of `start`. Ties in halite
    amount are broken by picking the closer cell.

    board: a kaggle-environments Board object
    start: a Point to search around
    radius: max Manhattan distance to search

    Returns: (best_pos, best_amount, best_distance, total_halite_in_radius)
      best_pos is a Point (may be `start` itself if nothing better is found).
    """
    size = board.configuration.size

    best_pos = start
    best_amount = board.cells[start].halite
    best_distance = 0
    total_halite = 0

    for dy in range(-radius, radius + 1):
        remaining = radius - abs(dy)
        for dx in range(-remaining, remaining + 1):
            x = (start.x + dx) % size
            y = (start.y + dy) % size
            pos = Point(x, y)
            distance = abs(dx) + abs(dy)

            amount = board.cells[pos].halite
            total_halite += amount

            if amount > best_amount or (amount == best_amount and distance < best_distance):
                best_pos, best_amount, best_distance = pos, amount, distance

    return best_pos, best_amount, best_distance, total_halite


def agent(obs, config):
    global _dock_target

    board = Board(obs, config)
    me = board.current_player
    size = board.configuration.size
    convert_cost = board.configuration.convert_cost
    spawn_cost = board.configuration.spawn_cost

    # Track halite we still have available to spend this turn.
    available_halite = me.halite

    shipyard_positions = [sy.position for sy in me.shipyards]

    # If we have ships but no shipyard, convert one to get started.
    if not me.shipyards and me.ships:
        starter = me.ships[0]

        if _dock_target is None:
            _dock_target = find_best_dock_site(starter, board, DOCK_SEARCH_RADIUS)

        if starter.position == _dock_target:
            if available_halite >= convert_cost:
                starter.next_action = ShipAction.CONVERT
                available_halite -= convert_cost
                _dock_target = None  # done, clear for safety
        else:
            starter.next_action = move_towards(starter.position, _dock_target, size)

    for ship in me.ships:
        if ship.next_action is not None:
            continue  # already assigned (e.g. converted above)

        if shipyard_positions and ship.halite >= CARGO_RETURN_THRESHOLD:
            # Head to the nearest shipyard to deposit cargo.
            nearest = min(
                shipyard_positions,
                key=lambda p: toroidal_distance(ship.position, p, size),
            )
            ship.next_action = move_towards(ship.position, nearest, size)
        else:
            # Otherwise mine or seek out halite.
            ship.next_action = best_neighbor_action(ship, board)

    # Spawn ships early to grow the fleet.
    if board.step < SPAWN_UNTIL_STEP:
        for shipyard in me.shipyards:
            if len(me.ships) >= MAX_SHIPS:
                break
            if available_halite >= spawn_cost:
                shipyard.next_action = ShipyardAction.SPAWN
                available_halite -= spawn_cost

    return me.next_actions