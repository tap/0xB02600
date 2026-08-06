# bot4.py — generation 4: influence fields, rate mining, farming

**Status: experiment concluded — architecture largely rejected.** Beats
three randoms decisively (32,683; 25 ships; 3 yards) but every variant
lost its head-to-head series against bot2. The shipped bot4.py is bot2's
economics plus the two surviving extras (endgame convert, small kill
bonus), with the rejected features left in the code but disabled by
constants. **bot2 remains the recommended submission.**

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

## The experiment log (all series 8 games, rotated seats, vs bot2)

| Variant | Result | Conclusion |
|---|---|---|
| v0 as designed (smoke test) | 47 vs 8,367 | Catastrophic vs a hunter despite 32k vs randoms |
| v0 + farming disabled | 3/8, mean −1,182 | **Farming as implemented is net-negative**: locking the home patch pushes miners on long trips through hunter territory, exactly where bot2's pirates operate. Recovered most of the gap. |
| v1: no farm, kill bonus 16→3, control steering off | 0/8, −3,251 | The suspected fixes did not close the gap (and may be partly noise — see control below). The +16 kill bonus genuinely dwarfed the ±1 distance scale, but taming it alone didn't rescue the variant. |
| v2: v1 + hunt weight 0.45→0.8 | 1/8, −1,417 | Matching bot2's hunting aggression isn't sufficient either. |
| v3: v2 + **bot2's mining formula** (drop rate-based scoring, control multiplier) | 3/8, −1,252 | Rate-based mining was a major structural drag: it over-favors distant rich cells, lengthening exposed trips. With bot2 economics restored the deficit shrinks to ~noise scale. |
| v4: v3 + bot2's hunting exactly (prey ≥100, no interception) = bot2 + convert trick + kill bonus 3 | 2/8, −1,878 | Even the "nearly bot2" reduction measured negative — motivating a bot2-vs-bot2 control series to establish the noise floor before reading any of these gaps as real. |

## Verdict

- **Rejected by evidence**: farming (as implemented), rate-based trip
  scoring, oversized kill incentives. These are kept in the file but
  gated off by constants, with the measurements documented here.
- **Unproven, likely neutral**: control-field steering, interception
  hunting — neither showed measurable value at this match budget.
- **Kept**: endgame convert (theoretically free EV: banks
  `cargo − 500` that would otherwise evaporate) and a small kill bonus.
- **Meta-lesson**: at this noise level (see the control series in
  docs/README.md), 8-game series can only detect large effects.
  Distinguishing "bot2 + ε" from bot2 would need 30+ paired games —
  not the best use of a hackathon evening.

## Open questions (for a future revisit)

- Does farming become viable with radius 1, a later start, or guards
  actually holding the plantation?
- Would interception hunting show value against a *fleeing-biased*
  opponent rather than bot2's own hunters?
