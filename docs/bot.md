# bot.py — generation 1: "stop self-destructing"

**Status: superseded by bot2** (kept as a fallback and as the baseline
the later bots were measured against).

## Design goal

Minimum viable fixes for the failure modes that killed the inherited
bots, shipped fast. No cleverness — just don't die, mine spread out,
bank cargo, and cash out before turn 400.

## Architecture

Single pass per turn, per-ship greedy decisions in cargo-descending
order:

1. **Yard creation** — walk the pioneer ship to the best dock site
   (radius-4 search scoring the surrounding radius-4 halite, minus 150
   per step walked; the candidate cell itself is excluded since
   conversion destroys its halite), convert on arrival, or convert in
   place if still yard-less by step 8.
2. **Per-ship targeting** — return home at ≥500 cargo or when the
   endgame recall triggers (`steps_left ≤ dist_home + 4`); otherwise
   claim the best unclaimed mining cell within radius 6, scored
   `halite / (1 + dist)`, skipping cells where a lighter enemy could
   reach us.
3. **Movement resolution** — score stay + 4 directions by negative
   distance-to-target; **refuse cells already reserved by a friendly
   ship** (the core anti-self-destruct mechanism); −1000 for any cell a
   lighter-or-equal enemy ship can reach; reserve the chosen cell.
   A cornered ship carrying ≥600 converts in place (conversion resolves
   before collision, banking the cargo).
4. **Spawning** — only onto un-reserved yard cells (the other core
   fix), fleet cap 15, stop spawning when `steps_left ≤ 90`, always
   respawn if the fleet hits zero with 30+ steps left.

## Key decisions

- **Reservation set over global planning.** Ships plan sequentially,
  loaded ships first; each reserves its destination. Simple, safe, and
  sufficient to eliminate friendly fire entirely. Also its ceiling:
  early-planned ships steal targets from later ones (fixed in bot2).
- **Threat = any enemy with ≤ our cargo within distance 1** of a
  candidate cell. Binary and conservative; ships never contest space.
- **No offense at all.** Pure economy. This is why bot2's hunters
  suppress it so hard (2–6k when facing bot2, vs 27–82k in soft
  fields).

## Measured results

| Series | Result |
|---|---|
| vs claude/google/starter | 1st, 8,359 (all three eliminated) |
| vs 3 randoms (×2) | 1st, 27,635 and 65,379 |
| Mixed field, different seat | 1st, 81,936 |
| vs bot2 (8 games, rotated seats) | mean ~11k vs bot2's ~40k across the 4-game series; 0 wins |

Never eliminated, never errored, well under the 3 s/turn limit.
