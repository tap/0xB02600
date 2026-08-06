# bot5.py — generation 5: graded repulsion

**Status: under evaluation** (head-to-head vs bot2 and a league run in
progress; results will be recorded here).

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

*(pending — series and league running)*
