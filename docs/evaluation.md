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

## Four-way tournament-realistic fields

The real tournament is a 4-player free-for-all, and 4-player dynamics
are nonlinear (aggression that wins one field loses another), so these
fields matter more than any 1v1. Runner: `eval/fourway.py` (12 games,
all seat rotations, reports wins / mean rank / mean halite). Note the
scores here are far below bot2's vs-random tens of thousands — a field
of capable bots suppresses everyone's economy, so games are
lower-scoring and higher-variance. Read *rank*, and prefer sweeps over
split results.

### colton / gavin / pacifist / bot2

Colton's bot (from main) is a **fork of bot2** — its source docstring is
bot2's verbatim, from the "Improvements based upon bot2" commit. It is
the strongest real entrant tested: 35,060 vs three randoms, in bot2's
own class. In the four-way, though, bot2's tuning still edges it:

| Bot | Wins | Mean rank | Mean halite |
|---|---|---|---|
| **bot2** | **12/12** | **1.00** | 4,714 |
| colton | 0/12 | 2.50 | 320 |
| pacifist | 0/12 | 2.67 | 387 |
| gavin | 0/12 | 3.83 | −60 |

bot2 won **every** game across all seat rotations — a far stronger
signal than a split result. colton clearly beats gavin and pacifist but
cannot take a game off bot2. This is the most reassuring result for the
tournament: bot2 cleanly handles the strongest actual competitor, not
just broken bots and personas.

### pacifist / gavin / bot2 / pirate (the "all-fighters" field)

Prompted by a single observed game where the pacifist won. Over 12
rotated games it does **not** hold up:

| Bot | Wins | Mean rank | Mean halite |
|---|---|---|---|
| pirate | 8/12 | 1.50 | 1,651 |
| bot2 | 4/12 | 1.75 | 1,055 |
| pacifist | 0/12 | 3.00 | 221 |
| gavin | 0/12 | 3.75 | −111 |

Lessons:

- **The pacifist "win" was noise.** Real single game, unrepresentative
  sample — over 12 games it averages 3rd and never wins. This field is
  a very low-score brawl (winner ~1,651), so single-game upsets are
  common; the trend is what counts.
- **Field-dependence is real.** The most aggressive bot (pirate) won
  *this* field, the opposite of the third-party hypothesis, while bot2
  won the colton field. Same bots, different mix, different winner —
  which is exactly why an opponent-adaptive detector tuned to one
  anecdote would backfire (it would have suppressed the aggression that
  wins here).
- **bot2 is top-two in both fields**, which is the property that
  matters going into an unknown 4-player table.

## Adaptation experiment: hunt the runaway leader

Idea: detect a runaway winner (the pacifist's one-game upset) and send
attacks to bring it down. `corpus/leaderhunt.py` is bot2 plus a
detector — past step 60, if any opponent's total wealth (bank + cargo)
exceeds ours by 15%, it focuses hunting on that leader's ships (cargo
threshold dropped 100 → 40, hunt weight ×3, packs of 3). Runner:
`eval/passivefield.py` (X + pacifist + pacifist + turtle, the field
most likely to produce a runaway).

**Result: not worth adopting.**

| Test | Finding |
|---|---|
| Regression vs bot2 (competitive field, 8 games) | 2/8, mean 871 vs 1,510 (−640) — inside the ±744 noise floor; no gain, slight lean negative |
| Passive field, leaderhunt vs plain bot2 (same field) | **identical mean rank 1.38**, but leaderhunt banked **1,321 vs bot2's 1,888** — same placement, less halite |

Two reasons it fails:

1. **Kingmaker cost.** In a 4-player game the attacker pays the full
   price of hunting the leader while the other two share the benefit.
   leaderhunt knocks first place down but ends up poorer at the same
   rank — visible as the lower mean halite for identical placement.
2. **The premise rarely fires against bot2.** A passive economy almost
   never *becomes* the runaway when bot2 is present — bot2's normal
   mining + general hunting already beats it (rank 1.38, 6/8 wins with
   no special logic). The pacifist "runaway" was a rare noise game, not
   an exploitable recurring state.

Same lesson as bot4/bot5/bot6: a plausible, well-targeted adaptation
that measurement rejects. bot2's existing hunting handles economic
opponents; special-casing the leader burns halite for no placement gain.

## Shipyard-raider stress test

Question: how does bot2 fare against a bot *designed to attack
shipyards*? `corpus/raider.py` keeps a mining core for income and
streams empty ships at the enemy's yards, piling `RAIDERS_PER_YARD = 3`
onto one yard to overwhelm a single defensive spawn. Trace tooling:
`eval/raid_trace.py` (instrumented 2-player game logging bot2's yard
count, shields, and bank each turn).

**Result: raider 0/8 vs bot2 (with random fillers), eliminated in 6 of
8 games; bot2 averaged 56,154 — higher than against most opponents.**

The mechanism, from the 2-player trace:

1. **The attack lands.** Three empty raiders beat bot2's single
   defensive-spawn blocker and ground its first yard's shields
   3 → 2 → 1 → 0, **destroying it at step 28** (bot2 at 319 halite,
   below the 500 spawn cost, so it could not out-spawn the pressure).
2. **bot2 rebuilds in one turn.** Its "have ships but no yard → convert
   the richest-cargo ship" logic stood up a fresh 3-shield yard at step
   29 and kept expanding. The raider knocked that down too; bot2 just
   rebuilt again.
3. **The raider starves.** A yard kill costs 3 ships (1,500 halite) to
   remove a 500 halite yard that rebuilds from cargo already aboard a
   ship. The mining core can't refund that, so the raider withered from
   5 ships to 1 while bot2 snowballed to 21 ships / 3 yards / 7 shields.
4. **Failed attacks feed bot2.** Ships lost on collisions drop halite
   onto the board and hand cargo to the winner, so attacking bot2
   *raises* its score — the raider is an economic donor.

### Why bot2 is robust here (and the one real gap)

Robustness comes from **instant rebuild** (a lost yard is a one-turn
setback while ≥1 ship survives to convert) plus the **ruinous 3-shield
trade** (this fork makes yard-killing 3× costlier than vanilla Halite,
and the defensive spawn forces even more attacker ships per yard).

The one genuine vulnerability the trace exposed: at step 28 bot2 lost
its **only** yard with the bank under 500. It survived solely because
it still had ships to convert. An attacker that destroys bot2's last
yard *in the same window where bot2 has no surviving ship and < 500
halite* would trigger the elimination rule. That window is narrow
(mostly the first ~8 turns before bot2 has a fleet), and closing it
requires hunting bot2's ships and its yards at once — i.e. a strong
all-around aggressor, which bot2's reservation-and-danger core has
beaten in every series run this session.

## bot2 vs the Gavin field

Series: bot2 + gavin + gavin_fixed + starter_fixed, 8 games, rotated
seats.

**bot2 won 8/8**, banking 16,199–76,079 per game. Both Gavin versions
finished between −277 and +311 (negative = eliminated), and
starter_fixed was eliminated every game (its remaining failure mode:
fleet convergence — the spawn fix alone doesn't stop ships
tie-colliding on shared targets).

Takeaways:

- Against the one confirmed real opponent, bot2's margin is total; the
  heat-map fix doesn't rescue Gavin's bot because its uncapped
  spawning drains the bank faster than its miners refill it.
- The "poor prey" concern (Gavin's ships bank at 100, starving our
  ≥100-cargo hunters) did not matter — the economic engine alone
  decides these games.
- starter_fixed being eliminated every game suggests the median
  competitor tomorrow needs BOTH classic fixes (spawn discipline and
  friendly-collision avoidance) to even survive; bots with only one
  fix still feed the field.
