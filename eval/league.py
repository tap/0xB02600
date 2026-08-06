"""Opponent-corpus league.

Each candidate plays every composition with all 4 seat rotations.
Reports mean rank, P(1st), eliminations, and mean halite per
(candidate, composition) — rank distribution is the honest metric since
tournament scoring is placement-based.
"""
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

SCRATCH = "/tmp/claude-0/-home-user-0xB02600/cdfda1a8-9935-514b-a0c4-fcc97f43fd4d/scratchpad"
KAGGLE = f"{SCRATCH}/hackathon/hackathon/kaggle-environments"
REPO = "/home/user/0xB02600"

CANDIDATES = {
    "bot2": f"{REPO}/bot2.py",
    "bot4": f"{REPO}/bot4.py",
    "earlydef": f"{SCRATCH}/corpus/earlydef.py",
}
COMPOSITIONS = {
    "weak":    [f"{SCRATCH}/corpus/starter_fixed.py", f"{REPO}/google.py", "random"],
    "persona": [f"{SCRATCH}/corpus/turtle.py", f"{SCRATCH}/corpus/pirate.py", f"{SCRATCH}/corpus/pacifist.py"],
    "strong":  [f"{REPO}/bot2.py", f"{SCRATCH}/corpus/pirate.py", f"{SCRATCH}/corpus/starter_fixed.py"],
}
ROTATIONS = 4


def play(cand_path, field, rotation):
    sys.path.insert(0, KAGGLE)
    from kaggle_environments import make
    agents = [cand_path] + field
    seated = agents[rotation:] + agents[:rotation]
    env = make("halite")
    env.run(seated)
    final = env.steps[-1]
    rewards = [s.reward if s.reward is not None else -9999 for s in final]
    cand_seat = seated.index(cand_path)
    cand_reward = rewards[cand_seat]
    rank = 1 + sum(1 for i, r in enumerate(rewards) if i != cand_seat and r > cand_reward)
    return cand_reward, rank


def main():
    jobs = []
    for cname, cpath in CANDIDATES.items():
        for compname, field in COMPOSITIONS.items():
            for rot in range(ROTATIONS):
                jobs.append((cname, compname, cpath, field, rot))

    results = {}
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(play, cpath, field, rot): (cname, compname)
            for cname, compname, cpath, field, rot in jobs
        }
        done = 0
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                results.setdefault(key, []).append(fut.result())
            except Exception as e:
                results.setdefault(key, []).append((None, None))
                print(f"ERROR {key}: {e}", file=sys.stderr)
            done += 1
            print(f"[{done}/{len(jobs)}]", file=sys.stderr, flush=True)

    print(f"{'candidate':10s} {'field':8s} {'mean_rank':>9s} {'P(1st)':>7s} {'elims':>5s} {'mean_halite':>11s}")
    for cname in CANDIDATES:
        agg_ranks, agg_first, agg_elims, n_all = [], 0, 0, 0
        for compname in COMPOSITIONS:
            games = [g for g in results.get((cname, compname), []) if g[1] is not None]
            if not games:
                print(f"{cname:10s} {compname:8s}  ALL ERRORED")
                continue
            ranks = [g[1] for g in games]
            rewards = [g[0] for g in games]
            firsts = sum(1 for r in ranks if r == 1)
            elims = sum(1 for r in rewards if r < 0)
            print(f"{cname:10s} {compname:8s} {sum(ranks)/len(ranks):9.2f} "
                  f"{firsts}/{len(games):<5d} {elims:5d} {sum(rewards)/len(rewards):11.0f}")
            agg_ranks += ranks
            agg_first += firsts
            agg_elims += elims
            n_all += len(games)
        if n_all:
            print(f"{cname:10s} {'ALL':8s} {sum(agg_ranks)/n_all:9.2f} "
                  f"{agg_first}/{n_all:<5d} {agg_elims:5d}")
        print()


if __name__ == "__main__":
    main()
