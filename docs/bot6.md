# bot6.py — Gavin's gradient bot, repaired

**Status: under evaluation** (fixes verified vs randoms; series vs bot2
and gavin-v2 running).

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
  was eliminated (−112), so a collision/elimination edge case remains
  under aggressive play.
- vs bot2 (6 games): *pending*
