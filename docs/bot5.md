# bot5.py — generation 5: graded repulsion

**Status: experiment concluded — parity with bot2, no demonstrated
gain.** v1 (gradient on all ships) measured an outright penalty; the
v2 refinement (laden ships only, half weight) recovered to parity
(3/8, −322, inside the ±744 noise floor) and is the configuration now
in bot5.py. **bot2 remains the recommended submission** — bot5 is the
better starting point only if a future evening brings the 30+ game
budget needed to tune the gradient properly.

## Design goal

Test the one promising idea from Gavin's heat-seeking gradient bot,
grafted onto bot2's proven engine: replace *cliff-edge* danger with a
*gradient*. It is also the refined form of the early-defense
hypothesis: the earlydef experiment showed hard early caution (bank at
300, radius-2 avoidance) helps against moderate fields but strangles
the economy under strong hunter pressure — so bot5 applies soft,
continuous pressure instead of hard rules.

## The single change from bot2

Movement scoring gains one term. For each candidate cell, every enemy
ship light enough to beat this ship in a collision (`enemy cargo ≤
ours`) pushes on it with strength `(4 − d)` for `d ≤ 3`, summed over
threats and scaled by a phase weight:

- `REPULSION_EARLY = 0.5` while `step < 100` — early robbery snowballs
  (measured: mirror games are bimodal), so laden ships give pirates a
  wide berth while the economy compounds.
- `REPULSION_LATE = 0.25` afterwards — established economies can
  afford to work closer to the frontier.

The hard wall (−1000 for any cell a lighter enemy can reach this turn)
stays underneath: the gradient only ranks *already-survivable* moves,
so a returning miner picks the home path that trends away from pirate
country before there's an emergency, instead of reacting one step from
death.

Distance units calibrate the strength: moving one step off the direct
path costs 1 point, so an adjacent lighter enemy (3 × 0.5 = 1.5 early)
justifies a one-step detour, and stacked threats justify longer ones.

## Why this and not the control field

bot4's control field (measured ≈ neutral) was a *global ownership* map,
blind to cargo matchups. bot5's gradient is per-ship and cargo-relative
— the same cell is dangerous to a laden miner and irrelevant to an
empty hunter — which is what actually determines collision outcomes.

## Results

### v1 (as committed: all ships, weights 0.5/0.25)

| Series | Result |
|---|---|
| Head-to-head vs bot2 (8 games) | **1/8**, mean 1,007 vs 2,868 (−1,862) — worse than the identical-copies control (1/8, −744), so likely a real small penalty |
| League: weak field | rank 1.00, 4/4 firsts (everyone sweeps this) |
| League: persona field | 2.50 — identical to bot2 |
| League: strong field | 2.25 vs bot2's 1.75, **1 elimination** (bot2 had 0) |

Suspected drag: the gradient applies to *empty* ships too — for a
0-cargo ship every enemy empty ship is a "threat," so hunters are
pushed away from the crowds they should be working, and early miners
detour around harmless traffic.

### v2 refinement (laden-only ≥100 cargo, half weights — now in bot5.py)

| Series | Result |
|---|---|
| Head-to-head vs bot2 (8 games) | **3/8**, mean 1,067 vs 1,389 (−322) — inside the noise floor: parity |

Restricting the gradient to laden ships recovered v1's penalty,
confirming the hunter-drag diagnosis, but no advantage emerged.

## Verdict

Graded repulsion joins the control field and interception hunting in
the "plausible, unproven at hackathon match budgets" bin. The idea
remains attractive — it is the only mechanism tested that can express
*phase-dependent* caution without hard rules (earlydef showed hard
rules backfire under pressure) — but distinguishing it from bot2 needs
a much larger paired-series budget and probably joint tuning of
radius/weights. The measured lesson stands: every feature must beat
the incumbent in its own series before shipping, and at n=8 only large
effects are detectable.
