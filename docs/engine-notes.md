# Engine notes: exploits, edges, and defensive hardening

An audit of the vendored hackathon engine (`kaggle-environments`,
halite fork with 3-shield shipyards) for exploitable behavior. Read via
`halite.py` (interpreter) and `helpers.py` (`Board.next()` turn
resolution), confirmed with targeted test agents.

## No offensive exploit exists

Agents are isolated: each is handed an observation and returns only its
own action dict. There is no shared mutable state to corrupt and no way
to command another player's units.

| Attempted exploit | Result |
|---|---|
| Put `CONVERT`/moves on an opponent's ship IDs | Ignored — a player's action dict is only applied to that player's own asset IDs. Opponents kept all halite. |
| Drive a player's halite negative | Blocked by `assert player.halite >= 0` and self-limiting spawn/convert guards that re-read the balance each iteration. |
| Chain converts (one conversion funds another same turn) | Explicitly closed: `leftover_convert_halite` is withheld until all conversions resolve (developer comment confirms intent). |
| Negative / garbage numeric action | Helper maps any non-enum value to `None` (hold); no crash. |

## The real bug surface points inward

Malformed or slow output eliminates YOU, not the opponent. A test agent
returning the invalid action string `"TELEPORT"` was marked **`INVALID`**
(reward `None`) by a JSON-schema validation layer — last place, behind
even eliminated players. The rules PDF confirms the same fate for
errors and timeouts.

Self-sabotage traps to avoid:

- Emitting any action string outside `{CONVERT, SPAWN, NORTH, SOUTH,
  EAST, WEST}` → `INVALID` → last.
- Raising an exception on any turn → errored → last.
- Exceeding `actTimeout` (3 s) → errored → last.

**Defensive posture (the actual "exploit" to pursue):** guarantee our
submission never emits a bad action, never throws, never stalls. bot2
builds actions only through the helper API (valid enum names by
construction) and ran ~20 full games with zero INVALID/ERROR statuses
at ~75 ms/turn against the 3 s limit.

## Legal resolution-order edges (not bugs)

The turn resolves in a fixed order; using it is fair play. Most are
already in bot2:

- **Convert before collision** → a cornered laden ship converts to bank
  its cargo safely. *(used)*
- **Convert with < 500 bank** if ship cargo covers the cost. *(used)*
- **Spawn before collision** → spawn onto a threatened yard to
  body-block an adjacent raider. *(used — defensive-spawn exception)*
- **Smallest-halite ship wins a collision and steals half** → empty
  ships are weapons. *(used — hunting)*
- **Ships swap through each other** without colliding (collision groups
  by final cell only). *(used implicitly; minor untapped upside for
  tight formations)*

## Verdict

There is no negative-number-style bug to weaponize against the field,
and pursuing one risks disqualification for marginal-or-negative value.
The durable advantage is a robust economy that never errors.
