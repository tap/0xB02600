# Bot lineage

Bots for the 2026 AOEM hackathon (Kaggle Halite IV rules, 21×21 board,
4 players, 400 turns, most *deposited* halite wins; this fork gives
shipyards 3 shields).

| Bot | One-liner | Status |
|---|---|---|
| [`claude.py` / `google.py` / `starter.py`](inherited-bots.md) | Inherited starting points | Broken — lose to `random` |
| [`bot.py`](bot.md) | Safety fixes: don't self-destruct | Superseded by bot2 |
| [`bot2.py`](bot2.md) | Global target auction, hunting, expansion | **Recommended submission** |
| [`bot3.py`](bot3.md) | bot2 with sweep-tuned constants | Retired — validated worse than bot2 |
| [`bot4.py`](bot4.md) | Influence fields, rate mining, farming | Experiment concluded — reduced to bot2 + extras |
| [`bot5.py`](bot5.md) | Graded repulsion (grown from Gavin's gradient) | Retired — parity with bot2, no gain |
| [`gavin.py`](evaluation.md) | Gavin's heat-seeking gradient bot (from main) | Field sample; idea source for bot5 |

See also [engine-notes.md](engine-notes.md) — exploit audit and defensive hardening.

## How bots are evaluated

All results come from full 400-turn games using the vendored
`kaggle-environments` engine from the hackathon zip, run headlessly
(`scratchpad/run_match.py`, `battle.py`, `battle2.py`, `tune.py`).

- **Series, not single games.** Match noise is large. Two measured
  controls: in the tuning sweep, baseline-vs-baseline games swung
  ±1300+ halite with seat "wins" splitting 1/6; a dedicated 8-game
  series between two *literal copies of bot2* finished 1/8 with a
  −744 mean delta. Mirror games are bimodal — an early successful
  robbery snowballs. Consequently an 8-game series can only detect
  large effects (bot2 vs bot.py was 4/4 at ~10× margins); anything
  within ±1,000 mean delta is treated as parity.
- **Paired comparison.** Competing bots play in the *same* games
  (with `bot.py` and `random` filling the other seats), seats rotated
  across matches, so map luck largely cancels.
- **Elimination encoding.** A negative final reward is not "negative
  halite" — the engine encodes eliminated players as
  `step_eliminated − 401` so they rank behind survivors.

## Lessons learned (chronological)

1. **Friendly fire is the first killer.** Equal-cargo collisions destroy
   *both* ships. Every inherited bot died to spawning onto its own
   holding ship or to its whole fleet converging on one rich cell.
2. **Fleet size compounds.** Raising the cap from 15 (bot.py) to 25
   (bot2) and spawning nearly every early turn was the largest single
   win-rate lever.
3. **Hunting is load-bearing, not optional.** With hunting disabled a
   bot scored 169 vs its hunting twin's 6,620 in the same games — an
   unarmed miner economy gets robbed into irrelevance.
4. **One-factor sweeps mislead at this noise level.** Both "winning"
   constants from the 72-match sweep (return at 350, single hunters)
   lost their isolation series against the baseline (3/8 and 0/8).
   Published post-mortems (mlomb's Halite III) hit the same wall and
   moved to genetic/CLOP tuning with much larger budgets.
5. **Clever features can be net-negative against a strong opponent.**
   bot4's farming and oversized kill bonus each beat `random` fine and
   still lost to bot2 — features must be validated against the best
   bot available, not against weak fields.

## External references

- [0Zeta/HaliteIV-Bot](https://github.com/0Zeta/HaliteIV-Bot) — 4th
  place, the most detailed public rule-based writeup (roles, dominance
  maps, farming, interception hunting).
- [solverworld: Optimal Mining](https://www.kaggle.com/code/solverworld/optimal-mining)
  — closed-form "how many turns to sit on a cell".
- [mlomb's Halite III post-mortem](https://mlomb.dev/blog/halite-iii-postmortem)
  — profit/cost scoring, two-stage move assignment, tuning methodology.
