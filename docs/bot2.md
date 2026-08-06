# bot2.py — generation 2: global auction + offense

**Status: recommended tournament submission.** Beat bot.py 4/4
decisively; survived every challenge from bot3's tuned variants and
(so far) bot4.

## Design goals

Keep bot.py's safety core, replace its two biggest strategic ceilings:
per-ship greedy targeting and total pacifism. Add expansion and
aggressive spawn economics.

## Architecture

1. **Yard creation** — same dock-site logic as bot.py, plus:
   - *Rebuild*: if the fleet has ships but no yard mid-game, the
     richest-cargo ship converts (its cargo offsets the 500 cost and
     deposits instantly).
   - *Expansion*: up to 3 yards; a new one is justified at ≥10 ships
     per existing yard, ≥120 steps remaining, and bank ≥ 1000. The
     converting ship is chosen as the one ≥6 from every existing yard
     sitting in the richest radius-3 neighborhood — the yard goes where
     a miner already profitably is, cutting deposit travel.
2. **Global target auction** (the headline change) — every (ship,
   target) pair is scored into one list, sorted best-first, and
   assigned greedily fleet-wide:
   - *Mining bids*: `halite / (1 + dist_to_cell + 0.4 · dist_cell_to_yard)`
     over **all** board cells ≥20 halite (not a radius around the
     ship), skipping threatened cells. One ship per cell.
   - *Hunting bids* (empty ships only): `0.7 · prey_cargo / (1 + dist)`
     against enemy ships carrying ≥100. Up to **2 hunters per prey** —
     one chaser never corners anything.
   - Forced tasks bypass the auction: return home at ≥500 cargo
     (≥200 when `steps_left < 100`), opportunistic top-up deposit when
     carrying ≥300 within distance 2 of a yard, endgame recall.
3. **Movement resolution** — inherited from bot.py (priority order,
   reservations, −1000 danger, cornered-convert escape), plus:
   an empty ship parked on its own yard steps off to the richest safe
   adjacent cell so it never blocks spawning.
4. **Spawning** — fleet cap **25** while `steps_left > 200`, 18 until
   120, then 0; hard stop at `steps_left ≤ 70` (a 500-cost ship can't
   pay back after that). *Defensive exception*: an enemy ship within 2
   of a yard triggers a spawn regardless of cap — the fresh 0-cargo
   ship is a perfect bodyguard.

## Key decisions

- **Auction over Hungarian.** Greedy-on-the-global-matrix captures most
  of the assignment-problem win in ~20 lines with no failure modes.
- **Hunting weight 0.7 / min prey 100 / packs of 2** — all three later
  re-validated by sweep + isolation series (hunting off lost 169 vs
  6,620; packs of 1 lost 0/8).
- **Fleet cap 25** — sweep-confirmed against 18 (−1955) and 32 (−830).

## Measured results

| Series | Result |
|---|---|
| vs bot.py + fillers (4 games, rotated seats) | 4/4 wins: 32,025 / 33,681 / 43,430 / 95,533 vs bot.py's 2,465 / 5,842 / 2,188 / 34,584 |
| vs bot3 (8 games) | 6/8 wins, mean +512 |
| vs bot3 single-change variants (8 games each) | 5/8 (+605) and 8/8 (+1,056) |
| vs bot4 v0 (smoke) / v0-nofarm (8 games) | 8,367 vs 47; 5/8 wins, mean +1,182 |

## Known weaknesses

- Movement is still priority-ordered, not jointly solved.
- Binary danger model: never contests space it could win with support.
- No farming: strips its own home patch, forfeiting regeneration
  compounding (though attempts to fix this in bot4 have so far cost
  more than they gained against hunting opponents).
- Hunters chase the prey's current cell rather than intercepting.
