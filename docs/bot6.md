# bot6.py — Gavin's gradient bot, repaired

**Status: evaluated. A large improvement over Gavin's bot, but not a
challenger to bot2.** Beats gavin-v2 5/6, yet is eliminated by bot2 in
all 6 games — the gradient fleet is fragile under sustained hunting.
**bot2 remains the recommended submission.**

## Lineage

`gavin.py` (Gavin, on main — the "v2" with the heat-map bug already
fixed) → `bot6.py`. The gradient identity is preserved verbatim:
`rate_cell` and `rate_shipyard` are Gavin's functions unchanged. bot6
repairs the mechanics around them, from the review in this session.

## The bug that mattered most

Gavin's v2 mines a fortune and banks almost none of it — it finished
games with ~200 halite banked while carrying 1,500+ undeposited on
ships (worth zero at turn 400). Two root causes, and a third found
while fixing:

1. **`move_towards` froze in congestion.** It returned `None` (hold)
   whenever the preferred step was blocked by a friendly ship, instead
   of detouring. In a dense fleet, homebound ships never reached the
   yard. → Rewritten to try every distance-reducing direction, farther
   axis first, returning the first free one.
2. **`going_home` never cleared when stuck.** A frozen ship stayed
   flagged forever, retrying the same blocked move. → A ship that can't
   advance is released from the homebound set (except during endgame
   recall) and falls back to a safe hold.
3. **The return threshold ran negative.** `200 − (10 + 0.1·step)·dist`
   goes below zero past mid-game, so `cargo >= threshold` was **always
   true** — every ship, even empty ones, flagged "going home" and the
   economy stalled. → Floored at `RETURN_FLOOR`, empty ships never sent
   home. This single change moved the vs-randoms result from 213 to
   5,103 banked.

## Other fixes

4. **Expansion capped and spaced.** v2 built ~4 clustered yards by step
   ~120 (2,000 halite sunk, yards overlapping). → `MAX_YARDS = 3`, a
   minimum spacing (`EXPAND_MIN_DIST`), a fleet-size gate, and a
   too-late cutoff.
5. **Real ship cap + late-game spawn stop.** v2 had `MAX_SHIPS`
   commented out (unbounded spawning). → cap restored at 22, hard stop
   at `steps_left ≤ 70`, plus a defensive spawn when an enemy is
   adjacent to a yard.
6. **Endgame recall added.** Ships bank everything before turn 400.
7. **Debug prints removed** (one was in the per-cell hot loop).

## What was deliberately kept

- The radius-7 gradient (`rate_cell`): halite attraction, +2 for
  huntable heavier enemies, −2 for threats/allies, distance falloff.
  This is the bot's identity and the most distinctive design in the
  field.
- Gavin's yard-site scoring and deadlock-aware spawn checks.

## Results

- vs 3 randoms: 213 → **5,103** banked after the return-logic fix;
  survives with a stable ~22-ship / 3-yard economy, no errors.
- **vs gavin-v2 (6 games): 5/6, mean 3,510 vs 374** — a ~9× gain over
  the version it was forked from; the fixes clearly land. One game bot6
  was eliminated (−112), foreshadowing the fragility below.
- **vs bot2 (6 games): 0/6, eliminated in ALL six** (rewards −67 to
  −232 vs bot2's 6,652–42,731). The gradient fleet does not survive
  sustained hunting.

## Why it beats Gavin but loses to bot2

The fixes solved Gavin's *self-inflicted* problems (frozen deposits,
economy-stalling return logic, cargo lost at the finish), which is why
it now crushes gavin-v2 and randoms. But bot6 keeps Gavin's structural
weaknesses that only a strong opponent punishes:

1. **Reactive, radius-limited defense.** `rate_cell` only repels
   threats it can see in its window and only when choosing a move; it
   has no global reservation system, so bot2's coordinated hunters trap
   ships that individually "felt safe."
2. **Big fragile fleet.** Uncapped-style spawning (even capped at 22)
   plus 3 yards spreads a large, thinly-defended fleet that feeds
   cargo — and half-cargo on every kill — straight to bot2's pirates.
3. **No danger *wall*, only a gradient.** Unlike bot2, a bot6 ship will
   still step somewhere merely "low-scoring" rather than treating a
   losing collision as forbidden, so it loses ships it didn't have to.

The elimination cascade: lost ships drop cargo bot2 collects, bot2
snowballs, and bot6's remaining fleet can't out-mine the bleeding.

## Verdict

bot6 is a successful *code review deliverable* — it proves the fixes to
Gavin's bot work, turning a 200-halite hoarder into a multi-thousand
economy that beats its parent 5/6. It is not a submission candidate:
against a coordinated hunter it has the same fate as every other bot
that lacks bot2's reservation core and danger wall. The lesson mirrors
bot4/bot5 — a distinctive strategy still needs the safety core to
survive the top of the table.
