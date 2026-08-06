"""Halite tournament bot, sixth generation.

Gavin's heat-seeking gradient bot (gavin.py on main, v2) with the fixes
found in review (see docs/bot6.md). The gradient identity is preserved
verbatim -- rate_cell / rate_shipyard are Gavin's -- and the mechanics
around them are repaired:

  1. move_towards now routes AROUND congestion (tries every distance-
     reducing direction) instead of giving up and freezing.
  2. Homebound ships that can't advance are released rather than staying
     flagged forever, and always fall back to a safe hold.
  3. Endgame recall: ships bank everything before turn 400, where
     undeposited cargo scores zero -- the single biggest score leak.
  4. Shipyard expansion is capped and spaced instead of building four
     clustered yards by step ~120.
  5. A real ship cap with a late-game spawn stop (a 500-cost ship can't
     repay itself near the end).
  6. Debug prints removed.

Lineage: gavin.py (Gavin) -> bot6.py.

Run locally:
    uv run --script run-viewer.py bot6.py bot2.py random random
"""

from kaggle_environments.envs.halite.helpers import *
import math

# --- Tunable strategy parameters --------------------------------------------
CARGO_RETURN_THRESHOLD = 350   # cargo at which a ship heads home to deposit
RETURN_FLOOR = 60              # never send a near-empty ship home to deposit
RETURN_DIST_SCALE = 15         # deposit a bit sooner when close to a yard
MINE_MIN_HALITE = 50           # only bother mining a cell with at least this much
MAX_SHIPS = 22                 # stop spawning once we have this many ships
SPAWN_STOP_STEPS_LEFT = 70     # a new ship can't repay 500 after this
SHIPYARD_THRESHOLD = 2500      # bank needed before considering a new yard
MAX_YARDS = 3                  # hard cap on shipyards
EXPAND_MIN_DIST = 5            # a new yard must be at least this far from others
EXPAND_MIN_FLEET = 8           # don't expand until the fleet can use the yard
EXPAND_STOP_STEPS_LEFT = 120   # too late for a new yard to pay off
ENDGAME_MARGIN = 4             # slack turns when recalling cargo at game end

next_positions = []
going_home = []


def toroidal_distance(a, b, size):
    """Manhattan distance on a wrap-around board."""
    dx = min((a.x - b.x) % size, (b.x - a.x) % size)
    dy = min((a.y - b.y) % size, (b.y - a.y) % size)
    return dx + dy


def move_towards(origin, target, size, blocked):
    """Step from origin toward target, routing around blocked cells.

    Unlike the original, this tries EVERY direction that reduces distance
    to the target (farther axis first) and returns the first whose
    destination is free, so a homebound ship detours around friendly
    traffic instead of freezing. Returns None only if genuinely boxed in.
    """
    if origin == target:
        return None
    east = (target.x - origin.x) % size
    west = (origin.x - target.x) % size
    north = (target.y - origin.y) % size
    south = (origin.y - target.y) % size

    candidates = []  # (action, distance_along_that_axis)
    if east != 0 or west != 0:
        action = ShipAction.EAST if east <= west else ShipAction.WEST
        candidates.append((action, min(east, west)))
    if north != 0 or south != 0:
        action = ShipAction.NORTH if north <= south else ShipAction.SOUTH
        candidates.append((action, min(north, south)))
    # Prefer closing the axis we're farther along; it spreads paths out.
    candidates.sort(key=lambda c: -c[1])

    for action, _ in candidates:
        npos = origin.translate(action.to_point(), size)
        if npos not in blocked:
            return action
    return None


def rate_cell(ship, cell, radius=7):
    """Gavin's gradient: halite attraction, prey +2, threats/allies repel."""
    score = 0.0
    if cell.ship and (cell.ship.player == ship.player or cell.ship.halite < ship.halite):
        return -1
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            tmp = cell.neighbor(Point(x, y))
            value = tmp.halite / 100.0
            if tmp.ship and tmp.position != ship.position:
                if tmp.ship.halite > ship.halite and tmp.ship.player != ship.player:
                    value += 2.0  # hunt ships carrying more than us
                else:
                    value -= 2.0
            score += value / (1 + math.sqrt(x * x + y * y))
    return score


def rate_shipyard(ship, cell, radius=3):
    """Gavin's yard-site score: local halite, allies help, any yard -> reject."""
    score = 0.0
    for y in range(-radius, radius + 1):
        for x in range(-radius, radius + 1):
            tmp = cell.neighbor(Point(x, y))
            value = tmp.halite / 100.0
            if tmp.ship and tmp.position != ship.position:
                if tmp.ship.player == ship.player:
                    value += 1
            if tmp.shipyard:
                return 0
            score += value / (1 + math.sqrt(x * x + y * y))
    return score


def best_neighbor_action(ship, board):
    """Move toward the best-rated adjacent cell (or mine in place)."""
    global next_positions
    cell = ship.cell
    if cell.halite >= MINE_MIN_HALITE:
        return None  # worth mining, stay put

    cells = {
        ShipAction.NORTH: cell.north,
        ShipAction.EAST: cell.east,
        ShipAction.SOUTH: cell.south,
        ShipAction.WEST: cell.west,
    }
    options = {}
    for k in cells:
        if cells[k].position in next_positions:
            continue  # don't collide with a friendly ship's planned move
        rating = rate_cell(ship, cells[k])
        if rating > 0:
            options[k] = rating
    if not options:
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


def agent(obs, config):
    global next_positions, going_home

    board = Board(obs, config)
    me = board.current_player
    size = board.configuration.size
    convert_cost = board.configuration.convert_cost
    spawn_cost = board.configuration.spawn_cost
    steps_left = board.configuration.episode_steps - board.step - 1

    available_halite = me.halite
    shipyard_positions = [sy.position for sy in me.shipyards]
    next_positions = []

    # Enemy shipyards are lethal to step onto; avoid routing through them.
    enemy_yards = {sy.position for p in board.opponents for sy in p.shipyards}

    # If we have ships but no shipyard, convert one to get started.
    if not me.shipyards and me.ships and available_halite >= convert_cost:
        me.ships[0].next_action = ShipAction.CONVERT
        available_halite -= convert_cost

    # FIX 4: capped, spaced expansion instead of unlimited clustered yards.
    if (
        me.shipyards
        and available_halite > SHIPYARD_THRESHOLD
        and len(me.shipyards) < MAX_YARDS
        and len(me.ships) >= EXPAND_MIN_FLEET
        and steps_left > EXPAND_STOP_STEPS_LEFT
    ):
        best_ship, best_score = None, 0.0
        for ship in me.ships:
            if ship.next_action is not None:
                continue
            if min(toroidal_distance(ship.position, y, size)
                   for y in shipyard_positions) < EXPAND_MIN_DIST:
                continue
            score = rate_shipyard(ship, ship.cell)
            if score > best_score:
                best_score, best_ship = score, ship
        if best_ship is not None:
            best_ship.next_action = ShipAction.CONVERT
            available_halite -= convert_cost

    # Move ships.
    for ship in me.ships:
        if ship.next_action is not None:
            continue  # already assigned (converted above)

        if shipyard_positions:
            nearest = min(
                shipyard_positions,
                key=lambda p: toroidal_distance(ship.position, p, size),
            )
            nearest_distance = toroidal_distance(ship.position, nearest, size)
        else:
            nearest, nearest_distance = None, None

        # Deposited: arrived home, clear the homebound flag.
        if nearest_distance == 0 and ship.id in going_home:
            going_home.remove(ship.id)

        # FIX 3: endgame recall -- get everything home before turn 400.
        endgame_recall = (
            nearest is not None
            and ship.halite > 0
            and steps_left <= nearest_distance + ENDGAME_MARGIN
        )
        # FIX (review): Gavin's distance-scaled threshold ran negative past
        # mid-game, so cargo >= threshold was ALWAYS true and every ship --
        # even empty ones -- flagged "going home", stalling the economy.
        # Floor it, and never send an empty ship home.
        effective_threshold = max(
            RETURN_FLOOR,
            CARGO_RETURN_THRESHOLD - RETURN_DIST_SCALE * nearest_distance,
        ) if nearest is not None else 0
        threshold_met = (
            nearest is not None
            and nearest_distance > 0
            and ship.halite >= effective_threshold
        )

        if ship.id in going_home or endgame_recall or threshold_met:
            blocked = set(next_positions) | enemy_yards
            action = move_towards(ship.position, nearest, size, blocked)
            # FIX 2: don't step into a lighter enemy; if we can't advance,
            # release the homebound flag so we don't freeze here forever.
            if action is not None:
                target_cell = board.cells[
                    ship.position.translate(action.to_point(), size)
                ]
                if target_cell.ship and target_cell.ship.halite < ship.halite \
                        and target_cell.ship.player_id != me.id:
                    action = None
            if action is not None:
                ship.next_action = action
                if ship.id not in going_home:
                    going_home.append(ship.id)
            else:
                # Boxed in this turn: hold, and stop insisting on the trip.
                if ship.id in going_home and not endgame_recall:
                    going_home.remove(ship.id)
        else:
            ship.next_action = best_neighbor_action(ship, board)

        next_positions.append(get_position(ship.cell, ship.next_action))

    # FIX 5 + spawn safety: real cap, late-game stop, no self-collision.
    want_ships = len(me.ships) < MAX_SHIPS and steps_left > SPAWN_STOP_STEPS_LEFT
    for shipyard in me.shipyards:
        if available_halite < spawn_cost:
            break
        # Never spawn onto a ship or a cell a ship is moving into.
        if any(s.position == shipyard.position for s in me.ships):
            continue
        if shipyard.position in next_positions:
            continue
        # Don't spawn into a fully boxed-in yard (deadlock).
        if (shipyard.cell.north.ship and shipyard.cell.south.ship
                and shipyard.cell.east.ship and shipyard.cell.west.ship):
            continue
        # Defensive spawn: an enemy adjacent to the yard -> body-block it.
        enemy_adjacent = any(
            toroidal_distance(ep, shipyard.position, size) <= 1
            for p in board.opponents for ep in [s.position for s in p.ships]
        )
        if want_ships or enemy_adjacent:
            shipyard.next_action = ShipyardAction.SPAWN
            available_halite -= spawn_cost
            next_positions.append(shipyard.position)

    return me.next_actions
