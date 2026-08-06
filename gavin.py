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
import random, math

# --- Tunable strategy parameters --------------------------------------------
CARGO_RETURN_THRESHOLD = 200  # cargo at which a ship heads home to deposit
MINE_MIN_HALITE = 50           # only bother mining a cell with at least this much
MAX_SHIPS = 20               # stop spawning once we have this many ships
SPAWN_UNTIL_STEP = 400        # don't spawn new ships after this step
SHIPYARD_THRESHOLD = 2000

next_positions = []
going_home = []
making_shipyard = None

def toroidal_distance(a, b, size):
    """Manhattan distance on a wrap-around board."""
    dx = min((a.x - b.x) % size, (b.x - a.x) % size)
    dy = min((a.y - b.y) % size, (b.y - a.y) % size)
    return dx + dy


def move_towards(origin, target, size):
    """Return a single ShipAction stepping from origin toward target (or None)."""
    global next_positions

    if origin == target:
        return None
    east = (target.x - origin.x) % size
    west = (origin.x - target.x) % size
    north = (target.y - origin.y) % size
    south = (origin.y - target.y) % size
# Move along whichever axis we're farther from, closing the shortest way.
    if east != 0 or west != 0:
        if east < west:
            if (origin + Point(1, 0)) not in next_positions:
                return ShipAction.EAST
        elif (origin + Point(-1, 0)) not in next_positions:
            return ShipAction.WEST
    if north != 0 or south != 0:
        if north <= south:
            if (origin + Point(0, 1)) not in next_positions:
                return ShipAction.NORTH
        elif (origin + Point(0, -1)) not in next_positions:
            return ShipAction.SOUTH
    return None

def rate_cell(ship, cell, radius=7):
    score = 0.0
    if cell.ship and (cell.ship.player == ship.player or cell.ship.halite < ship.halite):
        return -1
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            tmp = cell.neighbor(Point(x, y))
            value = tmp.halite / 100.0 # add amount limited to 100 for moves from player?
            if tmp.ship and tmp.position != ship.position:
                # hunt ships with halite in them
                if tmp.ship.halite > ship.halite and tmp.ship.player != ship.player:
                    value += 2.0
                else:
                    value -= 2.0
            # distance falloff
            score += value / (1 + math.sqrt(x*x + y*y))
            # add clumping with allies
            # add star base distance
            # add algorithm for finding new starbase locations
        # add clumping with allies
        # add star base distance
        # add algorithm for finding new starbase locations
        # add overarching goals for weight adjustment with score gradient analysis
    return score

def rate_shipyard(ship, cell, radius=3):
    score = 0.0
    enemies = 0
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            tmp = cell.neighbor(Point(x, y))
            value = tmp.halite / 100.0
            if tmp.ship and tmp.position != ship.position:
                if tmp.ship.player != ship.player:
                    enemies += 1
                else:
                    value += 1
            if tmp.shipyard:
                return 0
            # consider distance to other shipyards for overcrowding
            score += value / (1 + math.sqrt(x*x + y*y))
    #score += 3 - enemies
    return score


def best_neighbor_action(ship, board, available_halite):
    """Move toward the adjacent cell with the most halite (or mine in place)."""
    global next_positions

    cell = ship.cell
    # If the current cell is worth mining, stay put and collect.
    if cell.halite >= MINE_MIN_HALITE:
        print("just mining")
        return None

    cells = {
        ShipAction.NORTH: cell.north,
        ShipAction.EAST: cell.east,
        ShipAction.SOUTH: cell.south,
        ShipAction.WEST: cell.west,
    }

    options = {}

    for k in cells:
        # don't hit our teammates
        if cells[k].position in next_positions:
            continue
        rating = rate_cell(ship, cells[k])
        if rating > 0:
            options[k] = rating

    if len(options) == 0:
        print("no options")
        return None

    return max(options, key=options.get)


def get_position(cell, action):
    if action == ShipAction.NORTH:
        return cell.north.position
    if action == ShipAction.SOUTH:
        return cell.south.position
    if action == ShipAction.EAST:
        return cell.east.position
    if action == ShipAction.WEST:
        return cell.west.position
    return cell.position


def get_cell(cell, action):
    if action == ShipAction.NORTH:
        return cell.north
    if action == ShipAction.SOUTH:
        return cell.south
    if action == ShipAction.EAST:
        return cell.east
    if action == ShipAction.WEST:
        return cell.west
    return cell


def agent(obs, config):
    board = Board(obs, config)
    me = board.current_player
    size = board.configuration.size
    convert_cost = board.configuration.convert_cost
    spawn_cost = board.configuration.spawn_cost

    # Track halite we still have available to spend this turn.
    available_halite = me.halite

    shipyard_positions = [sy.position for sy in me.shipyards]
    global next_positions
    global going_home
    next_positions = []


    # If we have ships but no shipyard, convert one to get started.
    if not me.shipyards and me.ships and available_halite >= convert_cost:
        me.ships[0].next_action = ShipAction.CONVERT
        available_halite -= convert_cost

    # decide if we should build a new shipyard
    if available_halite > SHIPYARD_THRESHOLD:
        best_ship = None
        best_score = 0.0
        for ship in me.ships:
            score = rate_shipyard(ship, ship.cell, radius=3)
            if score > best_score:
                best_score = score
                best_ship = ship
        if best_score > 0:
            best_ship.next_action = ShipAction.CONVERT
            available_halite -= convert_cost
            print("making shipyard", ship.position)


    # analyze the current ships and pick one

    for ship in me.ships:
        if ship.next_action is not None:
            continue  # already assigned (e.g. converted above)

        nearest = min(
            shipyard_positions,
            key=lambda p: toroidal_distance(ship.position, p, size),
        )
        nearest_distance = toroidal_distance(ship.position, nearest, size)
        if nearest_distance < 1 and ship.id in going_home:
            going_home.remove(ship.id)
        if ship.id in going_home:
            ship.next_action = move_towards(ship.position, nearest, size)
            # try extra hard to avoid things
            test = get_cell(ship.cell, ship.next_action)
            if test.ship and test.ship.halite < ship.halite:
                ship.next_action = None
        else:
            if shipyard_positions and nearest_distance > 0 and ship.halite >= (CARGO_RETURN_THRESHOLD - ((10 + 0.1 * board.step) * nearest_distance)):
                ship.next_action = move_towards(ship.position, nearest, size)
                going_home.append(ship.id)
            else:
                # Otherwise mine or seek out halite.
                ship.next_action = best_neighbor_action(ship, board, available_halite)
        next_positions.append(get_position(ship.cell, ship.next_action))

    # Spawn ships early to grow the fleet.
    if board.step < SPAWN_UNTIL_STEP:
        for shipyard in me.shipyards:
            #if len(me.ships) >= MAX_SHIPS:
            #    break
            spawn = True
            # don't spawn if there's a ship on the yard
            for ship in me.ships:
                if ship.position == shipyard.position:
                    spawn = False
                    break
            # don't spawn if there's nowhwere to go
            if shipyard.cell.north.ship and shipyard.cell.south.ship and shipyard.cell.east.ship and shipyard.cell.west.ship:
                print("skipping spawn to avoid deadlock")
                spawn = False
            if shipyard.position in next_positions:
                print("skipping spawn to avoid collision")
                spawn = False
            if spawn and len(me.ships) > board.step / 20.0:
                spawn = random.randrange(0, 100) < 25
            if spawn and available_halite >= spawn_cost:
                shipyard.next_action = ShipyardAction.SPAWN
                available_halite -= spawn_cost

    return me.next_actions
