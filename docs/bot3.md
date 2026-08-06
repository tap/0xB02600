# bot3.py — generation 3: sweep-tuned constants

**Status: retired.** Identical to bot2 except two constants; validated
*worse* than bot2 head-to-head. Kept on the branch as a lab record of
the tuning methodology and its failure.

## What changed

| Constant | bot2 | bot3 | Sweep rationale |
|---|---|---|---|
| `CARGO_RETURN_THRESHOLD` | 500 | 350 | Bank sooner, less cargo exposed to hunters (won 5/6 sweep games, +323) |
| `HUNTERS_PER_PREY` | 2 | 1 | Lone chaser harasses nearly as well, frees a miner (won 5/6, +744) |

## The tuning experiment

A 72-match parallel sweep (`scratchpad/tune.py`): 11 single-constant
variants × 6 games each against the bot2 baseline **in the same games**
(fillers: bot.py + random, seats rotated), plus 6 baseline-vs-baseline
control games to measure noise.

Sweep conclusions that *did* hold up:

- `HUNT_WEIGHT`: 0.0 catastrophic (169 vs 6,620 — hunting is
  load-bearing), 0.35 bad, 1.2 mildly negative → 0.7 confirmed.
- `FLEET_CAP_EARLY`: 18 (−1955) and 32 (−830) both worse → 25 confirmed.
- `SPAWN_STOP_STEPS_LEFT`: 50 (−4518) and 100 (−2030) both worse → 70
  confirmed.

## Why bot3 failed anyway

The control games showed baseline-vs-baseline deltas of ±1300+ — the
same order as the "positive" signals for the two adopted changes.
Validation series told the real story:

| Series (8 games each, rotated seats) | Result vs bot2 |
|---|---|
| bot3 (both changes) | **2/8**, mean −512 |
| return-350 alone | **3/8**, mean −605 |
| hunters-1 alone | **0/8**, mean −1,056 |

Both "winning" constants were noise; single hunters in particular is
decisively wrong (packs of 2 corner prey, lone chasers don't).

## Lessons encoded in later work

1. Six games per variant is far below the noise floor of this game;
   only adopt a change after it survives a *dedicated* series against
   the incumbent.
2. Always run baseline-vs-baseline controls to know the noise scale
   before reading a sweep table.
3. Constants interact (the combined bot3 ≠ sum of its parts); tune
   jointly or validate combinations explicitly. Published post-mortems
   reached the same conclusion and used genetic/CLOP methods with much
   larger match budgets.
