# Inherited bots: `claude.py`, `google.py`, `starter.py`

The three bots present in the repo at the start. All three **lose to the
built-in `random` agent** — two get eliminated outright — which is what
prompted the rewrite lineage.

## Shared strategy shape

All three follow the same loop: convert the first ship to a shipyard,
spawn ships up to a cap, mine the current cell if rich enough, otherwise
move toward the richest nearby cell, and return home to deposit at
500 cargo.

- `starter.py` — the provided example. Dock-site search (radius 7,
  neighborhood scoring), 8-ship cap, adjacent-cell mining only.
- `claude.py` — starter variant: 20-ship cap, radius-5 richest-cell
  seek, spawn accounting that tracks this turn's spends.
- `google.py` — independent variant: converts on turn 1 at the spawn
  position with no site evaluation, 8-ship cap, and the only one with
  any friendly-collision avoidance (`occupied_next_cells`).

## Why they die

Verified by tracing fleet size per turn against three randoms:

1. **Spawn-over-holding-ship (all three).** A freshly spawned ship sits
   on the yard with 0 cargo. If nearby cells are below the 50-halite
   mining threshold, it "holds" — and the yard spawns again next turn on
   top of it. Equal-cargo collision destroys both. `starter.py` and
   `google.py` show a perfect 1→0→1→0 ship oscillation, burning 500
   halite per turn until the bank is empty and the player is eliminated.
   `google.py`'s reservation set doesn't prevent this because spawn
   decisions are made *before* ship moves are planned.
2. **Fleet convergence (`claude.py`, `starter.py`).** Every ship
   independently seeks "the richest cell within radius 5", so they all
   pick the same cell and tie-collide. `claude.py` builds 5 ships then
   collapses to 1 within a few turns.
3. **No endgame recall, no enemy awareness** — moot given 1 and 2.

## Measured results

| Match | Result |
|---|---|
| claude vs google vs starter vs random | random 1st (321); google 8; claude eliminated (~step 40); starter eliminated |
| Each vs 3 randoms (traced) | claude eliminated ~step 41; starter bank drained to 0 by step 16; google survives at ~84 |

A do-nothing bot that kept its starting 5,000 halite would have beaten
all three.
