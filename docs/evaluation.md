# Opponent corpus & league evaluation

How we prove a bot "generally performs well" rather than just beating
one sparring partner: a corpus of opponent archetypes and a league
runner that reports **rank distribution** (the tournament scores
placement, not halite) across fields of different strengths.

## The corpus (`corpus/`)

| Opponent | What it represents |
|---|---|
| `starter_fixed.py` | The median competitor: starter.py with only the spawn-suicide fixed and ships nudged off the yard |
| `donothing.py` | The floor: keeps its starting 5,000 — any submission must beat it |
| `turtle.py` | bot2 persona: small fleet (cap 10), banks at 250, barely hunts, one yard |
| `pirate.py` | bot2 persona: hunt weight 1.5, robs anything ≥50 cargo |
| `pacifist.py` | bot2 persona: never hunts, pure economy |
| `earlydef.py` | bot2 persona: banks at 300 + radius-2 caution for the first 100 steps, then relaxes |
| `gavin.py` (repo root, from main) | **Real field sample**: Gavin's heat-seeking gradient bot |
| `gavin_fixed.py` | Gavin's bot with its heat-map bug fixed (halite only counted on ship-occupied cells) and prints stripped — the version we might actually face |
| inherited bots, `random` | The bottom of the field |

Plus the lineage bots themselves (`bot.py`, `bot2.py`, `bot4.py`) as
strong opponents.

## League design (`eval/league.py`)

Each candidate plays every composition with all 4 seat rotations:

- **weak**: starter_fixed + google.py + random (most of the expected room)
- **persona**: turtle + pirate + pacifist (archetype coverage)
- **strong**: bot2 + pirate + starter_fixed (top-table pressure)

Metrics per (candidate, field): mean rank, P(1st), eliminations, mean
halite. The noise floor from the bot2-vs-bot2 control (1/8, −744) means
per-field numbers at n=4 are directional only; the aggregate over 12
games and *structural* events (eliminations) carry the weight.

## League results (2026-08-06)

| Candidate | weak | persona | strong | ALL (12 games) |
|---|---|---|---|---|
| **bot2** | rank 1.00, 4/4 firsts | 2.50, 1/4 | **1.75, 1/4** | **1.75, 6 firsts, 0 elims** |
| bot4 | 1.00, 4/4 | 3.50, 0/4, 1 elim | 2.00, 1/4, 1 elim | 2.17, 5 firsts, **2 elims** |
| earlydef | 1.00, 4/4 | **2.00, 2/4** | 3.00, 0/4 | 2.00, 6 firsts, 0 elims |

### Findings

1. **bot4's endgame convert was an elimination trap.** Converting the
   last ships near the finish with the bank under 500 triggers the
   elimination rule (no ships + <500 halite + the yards don't matter)
   and zeroes the entire game. Two league eliminations traced to this;
   fixed with a survival guard (keep one ship alive or leave ≥500 in
   the bank after converting).
2. **Early defense is half right.** `earlydef` (the hypothesis that
   robbery snowballs, so protect the early phase) beat bot2 in the
   persona field but collapsed against the strong field: radius-2
   avoidance plus short trips strangles the economy exactly when
   hunter pressure is highest. Verdict: *graded* caution (a soft
   repulsion field à la Gavin, phase-scaled) is the promising follow-up,
   not harder rules.
3. **All candidates sweep the weak field 4/4** — against the expected
   bulk of the room, the safety core alone is decisive.
4. **bot2 remains the submission**: best aggregate rank, zero
   eliminations, no archetype blind spot found.

## Gavin's bot: ideas adopted into the corpus

`gavin.py` scores each candidate move by a radius-7 weighted sum —
halite as attraction, heavier enemy ships as prey (+2), other ships as
repulsion (−2), with distance falloff. Graded steering rather than
binary danger. As committed it has a bug (halite only counts on cells
containing a ship), which `gavin_fixed.py` corrects for corpus use.
Its always-bank-at-100 style also makes its ships poor prey for our
≥100-cargo hunters — a deliberate archetype stress for hunting-reliant
strategies. A direct bot2-vs-Gavin-field series is recorded below.

## bot2 vs the Gavin field

*(series: bot2 + gavin + gavin_fixed + starter_fixed, 8 games, rotated
seats — results pending at time of writing; see final section of this
doc in a later commit.)*
