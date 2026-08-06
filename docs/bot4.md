# bot4.py — generation 4: influence fields, rate mining, farming

**Status: work in progress — does not yet beat bot2.** Beats three
randoms decisively (32,683; 25 ships; 3 yards) but loses head-to-head
to bot2. Diagnosis and repair in flight; bot2 remains the recommended
submission until bot4 wins a validation series.

## Design goals

A genuinely different architecture rather than more tuning, borrowing
from the published Halite IV playbook
([0Zeta 4th place](https://github.com/0Zeta/HaliteIV-Bot),
[solverworld's optimal mining](https://www.kaggle.com/code/solverworld/optimal-mining)):
shift from "greedy auction + binary danger" toward
"fields + trip-rate economics + territory".

## New mechanisms (vs bot2)

1. **Control field** — a blurred influence map: every friendly ship adds
   `(4 − d)/4` to cells within distance 4, every enemy subtracts it.
   Mining scores scale by `1 + 0.25·clamp(control)/2` so ships prefer
   dominated territory; movement (in v0) also read the field.
2. **Rate-based mining** — cells scored by halite-per-turn over the full
   round trip: `max over sit-lengths t of halite·(1 − 0.75^t) / (1 +
   travel + t + 0.3·return_leg)`. Replaces bot2's `halite/(1+dist)`
   with the actual "how long is this trip and what does it pay" math.
3. **Farming** — cells within radius 2 of an own yard are off-limits
   below 470 halite (between step 40 and the last 70 steps), letting 2%
   regeneration compound toward the 500 cap for an endgame harvest.
   This fork's 3-shield yards make plantations defensible in principle.
4. **Interception hunting** — hunters target the prey's *escape square*
   (its neighbor closest to its own nearest yard) instead of tailing
   its current cell; first hunter takes the escape square, second tails.
   Hunter head-count capped at fleet/4.
5. **Kill moves** — stepping onto a heavier enemy ship earns a movement
   bonus (we win that collision and steal half its cargo).
6. **Endgame convert** — a ship carrying ≥650 that cannot reach home in
   the remaining turns (or in the final 2 turns) converts in place,
   banking cargo − 500 that would otherwise evaporate at turn 400.

Safety core (reservations, spawn discipline, recall, cornered-convert)
carried over from bot2 unchanged, as are yard expansion and spawn
economics.

## What went wrong, so far

| Experiment | Result vs bot2 | Conclusion |
|---|---|---|
| v0 as designed (smoke test) | 47 vs 8,367 | Catastrophic vs a hunter despite 32k vs randoms |
| v0 with farming disabled (8 games) | 3/8, mean −1,182 | **Farming as implemented is net-negative**: locking the home patch pushes miners on long trips through hunter territory, exactly where bot2's pirates operate. Recovered most of the gap but not all. |
| v1: no farm + kill bonus 16→3 + control steering off; v2: v1 + hunt 0.45→0.8 (8 games each) | *pending — series running* | The +16 kill bonus dwarfed the ±1 distance scale, making any miner adjacent to a heavier enemy abandon its route to chase it indefinitely. |

## Open questions

- Does farming become viable with a smaller radius (1), a later start,
  or only once local control is positive (guards actually holding the
  plantation)?
- Is the control field worth keeping in mining scores even if it's
  removed from movement?
- Interception hunting vs bot2's naive chase: not yet isolated.
