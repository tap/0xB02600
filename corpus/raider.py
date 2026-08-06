"""Shipyard raider: an opponent designed to attack enemy shipyards.

Strategy for stress-testing bot2's yard defense in the 3-shield fork:
  * Keep a mining core for income (yards cost ships, ships cost halite).
  * Stream empty ships at the nearest enemy shipyard to grind its shields.
  * Prefer targets belonging to the strongest opponent (deny the leader),
    and pile 2-3 raiders on one yard so a defensive spawn can't tie them
    all -- if two empty raiders arrive and the defender only kills one,
    the second survives on the yard and drops a shield.
  * Spawn continuously to keep the pressure and the economy going.
"""
from kaggle_environments.envs.halite.helpers import (
    Board, Point, ShipAction, ShipyardAction,
)

MINE_MIN = 50
RETURN_CARGO = 400
RAIDER_FRACTION = 0.5     # share of the fleet assigned to raiding
RAIDERS_PER_YARD = 3      # pile enough to beat one defensive spawn
MAX_SHIPS = 24


def tdist(a, b, size):
    dx = min((a.x - b.x) % size, (b.x - a.x) % size)
    dy = min((a.y - b.y) % size, (b.y - a.y) % size)
    return dx + dy


def step_toward(origin, target, size, blocked):
    if origin == target:
        return None
    e = (target.x - origin.x) % size
    w = (origin.x - target.x) % size
    n = (target.y - origin.y) % size
    s = (origin.y - target.y) % size
    cands = []
    if e or w:
        cands.append((ShipAction.EAST if e <= w else ShipAction.WEST, min(e, w)))
    if n or s:
        cands.append((ShipAction.NORTH if n <= s else ShipAction.SOUTH, min(n, s)))
    cands.sort(key=lambda c: -c[1])
    for action, _ in cands:
        if origin.translate(action.to_point(), size) not in blocked:
            return action
    return None


def agent(obs, config):
    board = Board(obs, config)
    me = board.current_player
    size = board.configuration.size
    spawn_cost = board.configuration.spawn_cost
    convert_cost = board.configuration.convert_cost
    bank = me.halite

    # Establish a base.
    if not me.shipyards and me.ships and bank >= convert_cost:
        me.ships[0].next_action = ShipAction.CONVERT
        bank -= convert_cost
        return me.next_actions

    yard_pos = [sy.position for sy in me.shipyards]

    # Enemy shipyards, strongest opponent first (deny the leader).
    opp_by_halite = sorted(board.opponents, key=lambda p: -p.halite)
    enemy_yards = [sy.position for p in opp_by_halite for sy in p.shipyards]

    reserved = set()
    ships = me.ships
    n_raiders = int(len(ships) * RAIDER_FRACTION)
    # Empty ships closest to an enemy yard make the best raiders.
    def raid_key(s):
        if not enemy_yards:
            return 1e9
        return min(tdist(s.position, y, size) for y in enemy_yards) + s.halite / 100.0
    raiders = set(s.id for s in sorted(ships, key=raid_key)[:n_raiders]) if enemy_yards else set()

    assigned_per_yard = {}
    for ship in ships:
        pos, cargo = ship.position, ship.halite
        target = None

        if ship.id in raiders and enemy_yards:
            # Pick the nearest enemy yard not already over-subscribed.
            options = sorted(enemy_yards, key=lambda y: tdist(pos, y, size))
            for y in options:
                if assigned_per_yard.get(y, 0) < RAIDERS_PER_YARD:
                    target = y
                    assigned_per_yard[y] = assigned_per_yard.get(y, 0) + 1
                    break
            if target is None:
                target = options[0]
        else:
            # Mining core: bank cargo, else mine or seek halite.
            if yard_pos and cargo >= RETURN_CARGO:
                target = min(yard_pos, key=lambda y: tdist(pos, y, size))
            elif ship.cell.halite >= MINE_MIN:
                target = pos  # stay and mine
            else:
                best, best_h = pos, ship.cell.halite
                for d in (ship.cell.north, ship.cell.south, ship.cell.east, ship.cell.west):
                    if d.halite > best_h:
                        best, best_h = d.position, d.halite
                target = best

        if target == pos:
            reserved.add(pos)
            continue
        # Raiders are allowed to step onto the enemy yard (that's the attack);
        # miners avoid friendly collisions only.
        action = step_toward(pos, target, size, reserved)
        if action is not None:
            nxt = pos.translate(action.to_point(), size)
            ship.next_action = action
            reserved.add(nxt)
        else:
            reserved.add(pos)

    # Spawn to sustain pressure and economy.
    for sy in me.shipyards:
        if bank < spawn_cost or len(me.ships) >= MAX_SHIPS:
            break
        if sy.position in reserved:
            continue
        sy.next_action = ShipyardAction.SPAWN
        reserved.add(sy.position)
        bank -= spawn_cost

    return me.next_actions
