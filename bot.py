"""Halite tournament bot.

Fixes the failure modes found in claude.py / google.py / starter.py:

  * Never spawns a ship onto a cell a friendly ship will occupy (the old
    bots spawned on top of their own holding ships every turn -- equal-cargo
    collisions destroy BOTH ships, draining the bank until elimination).
  * Reserves every ship's next cell so friendly ships never tie-collide.
  * Ships claim distinct mining targets instead of all converging on the
    same richest cell and annihilating each other.
  * Avoids cells adjacent to enemy ships carrying less halite than us
    (they win the collision and steal half our cargo).
  * Recalls all cargo to a shipyard before the game ends -- undeposited
    halite is worth nothing at turn 400.

Run locally:
    uv run --script run-viewer.py bot.py random random random
"""

from kaggle_environments.envs.halite.helpers import (
    Board,
    Point,
    ShipAction,
    ShipyardAction,
)

# --- Tunable strategy parameters --------------------------------------------
MAX_SHIPS = 15                 # fleet size cap
SPAWN_MIN_STEPS_LEFT = 90      # stop spawning when a new ship can't pay back
CARGO_RETURN_THRESHOLD = 500   # cargo at which a ship heads home
LATE_RETURN_THRESHOLD = 250    # lower bar once the game is winding down
TARGET_SEARCH_RADIUS = 6       # how far ships look for mining targets
TARGET_MIN_HALITE = 25         # ignore cells with less halite than this
DOCK_SEARCH_RADIUS = 4         # first-yard site search distance
DOCK_EVAL_RADIUS = 4           # neighborhood scored around each dock candidate
DOCK_DIST_PENALTY = 150        # halite-equivalent cost per step walked to dock
CONVERT_DEADLINE = 8           # convert in place if still yard-less by this step
ENDGAME_MARGIN = 4             # slack turns when recalling cargo at game end
DANGER_PENALTY = 1000          # movement score penalty for entering a kill zone

_dock_target = None  # persists across turns within one episode

ALL_DIRECTIONS = [ShipAction.NORTH, ShipAction.EAST, ShipAction.SOUTH, ShipAction.WEST]


def toroidal_distance(a, b, size):
    """Manhattan distance on the wrap-around board."""
    dx = min((a.x - b.x) % size, (b.x - a.x) % size)
    dy = min((a.y - b.y) % size, (b.y - a.y) % size)
    return dx + dy


def cells_within(center, radius, size):
    """Yield (point, distance) for all cells within Manhattan `radius`."""
    for dy in range(-radius, radius + 1):
        remaining = radius - abs(dy)
        for dx in range(-remaining, remaining + 1):
            yield Point((center.x + dx) % size, (center.y + dy) % size), abs(dx) + abs(dy)


def find_dock_site(ship, board, size):
    """Pick the first shipyard location: richest neighborhood, close by.

    The candidate cell itself is excluded from the score because converting
    destroys the halite underneath, and each step walked costs turns, so
    distance carries a halite-equivalent penalty.
    """
    best_pos, best_score = ship.position, None
    for pos, dist in cells_within(ship.position, DOCK_SEARCH_RADIUS, size):
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

    halite_left = me.halite  # bank still unspent this turn

    # Enemy intelligence: (position, cargo) of every hostile ship, and the
    # set of enemy shipyard cells (sailing onto one destroys our ship).
    enemy_ships = [(s.position, s.halite) for p in board.opponents for s in p.ships]
    enemy_yards = {sy.position for p in board.opponents for sy in p.shipyards}

    def dangerous(pos, cargo):
        """True if an enemy ship that beats us in a collision can reach pos."""
        return any(
            ec <= cargo and toroidal_distance(ep, pos, size) <= 1
            for ep, ec in enemy_ships
        )

    # ---- Shipyard creation --------------------------------------------------
    converting = set()
    if not me.shipyards and me.ships:
        pioneer = me.ships[0]
        if _dock_target is None:
            _dock_target = find_dock_site(pioneer, board, size)
        # Convert on arrival, or in place if we've dithered too long / the
        # game is already under way (yard was destroyed mid-game).
        arrived = pioneer.position == _dock_target
        overdue = board.step >= CONVERT_DEADLINE
        if (arrived or overdue) and halite_left + pioneer.halite >= convert_cost:
            pioneer.next_action = ShipAction.CONVERT
            converting.add(pioneer.id)
            halite_left -= max(0, convert_cost - pioneer.halite)
            _dock_target = None

    yard_positions = [sy.position for sy in me.shipyards]

    # ---- Ship movement ------------------------------------------------------
    # Loaded ships plan first so they get right-of-way on contested cells.
    reserved = set()   # cells our ships will occupy next turn
    claimed = set()    # mining cells already assigned to a ship
    return_threshold = (
        CARGO_RETURN_THRESHOLD if steps_left > 100 else LATE_RETURN_THRESHOLD
    )

    for ship in sorted(me.ships, key=lambda s: -s.halite):
        if ship.id in converting:
            continue

        pos, cargo = ship.position, ship.halite

        # Choose a destination.
        home = min(
            yard_positions,
            key=lambda p: toroidal_distance(pos, p, size),
            default=None,
        )
        must_bank = home is not None and cargo > 0 and (
            cargo >= return_threshold
            or steps_left <= toroidal_distance(pos, home, size) + ENDGAME_MARGIN
        )
        if must_bank:
            target = home
        else:
            target = pos
            best_score = (
                board.cells[pos].halite
                if board.cells[pos].halite >= TARGET_MIN_HALITE
                and not dangerous(pos, cargo)
                else 0
            )
            for cand, dist in cells_within(pos, TARGET_SEARCH_RADIUS, size):
                if dist == 0 or cand in claimed or cand in enemy_yards:
                    continue
                halite = board.cells[cand].halite
                if halite < TARGET_MIN_HALITE or dangerous(cand, cargo):
                    continue
                score = halite / (1 + dist)
                if score > best_score:
                    target, best_score = cand, score
            claimed.add(target)

        # Score each move (stay + 4 directions): prefer closing on the
        # target, refuse cells our own ships reserved, punish kill zones.
        best_action, best_score = None, None
        fallback = None  # least-bad option if everything is reserved
        for action in [None] + ALL_DIRECTIONS:
            nxt = pos if action is None else pos.translate(action.to_point(), size)
            if nxt in enemy_yards:
                continue
            if nxt in reserved:
                continue
            score = -toroidal_distance(nxt, target, size)
            if dangerous(nxt, cargo):
                score -= DANGER_PENALTY
            if best_score is None or score > best_score:
                best_action, best_score = action, score
                fallback = nxt
        if fallback is None:
            fallback = pos  # fully boxed in by our own fleet: hold and hope

        # Cornered with a fat cargo: convert to a yard, banking it instantly
        # (conversion resolves before collision).
        boxed_in = best_score is not None and best_score <= -DANGER_PENALTY
        if (
            boxed_in
            and cargo >= convert_cost + 100
            and board.cells[pos].shipyard is None
        ):
            ship.next_action = ShipAction.CONVERT
            continue

        ship.next_action = best_action
        reserved.add(fallback)

    # ---- Spawning -----------------------------------------------------------
    # Never spawn onto a reserved cell: that is exactly the friendly
    # tie-collision that killed the older bots.
    fleet_size = len(me.ships)
    want_ships = fleet_size < MAX_SHIPS and (
        steps_left > SPAWN_MIN_STEPS_LEFT or (fleet_size == 0 and steps_left > 30)
    )
    if want_ships:
        for shipyard in me.shipyards:
            if fleet_size >= MAX_SHIPS or halite_left < spawn_cost:
                break
            if shipyard.position in reserved:
                continue
            shipyard.next_action = ShipyardAction.SPAWN
            reserved.add(shipyard.position)
            halite_left -= spawn_cost
            fleet_size += 1

    return me.next_actions
