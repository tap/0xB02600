"""Generic parallel series: argv[1] vs argv[2], bot.py + random as field."""
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

KAGGLE = "/tmp/claude-0/-home-user-0xB02600/cdfda1a8-9935-514b-a0c4-fcc97f43fd4d/scratchpad/hackathon/hackathon/kaggle-environments"
A, B = sys.argv[1], sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 8

def play(rotation):
    sys.path.insert(0, KAGGLE)
    from kaggle_environments import make
    agents = [A, B, "/home/user/0xB02600/bot.py", "random"]
    seated = agents[rotation:] + agents[:rotation]
    env = make("halite")
    env.run(seated)
    final = env.steps[-1]
    return {a: (final[i].reward or 0) for i, a in enumerate(seated)}

def main():
    results = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(play, m % 4) for m in range(N)]
        for f in as_completed(futs):
            results.append(f.result())
    a_wins = sum(1 for g in results if g[A] > g[B])
    ma = sum(g[A] for g in results) / len(results)
    mb = sum(g[B] for g in results) / len(results)
    na, nb = Path(A).name, Path(B).name
    for g in results:
        print(f"  {na}={g[A]:7.0f}   {nb}={g[B]:7.0f}")
    print(f"{na} beats {nb}: {a_wins}/{len(results)}   mean {ma:.0f} vs {mb:.0f}  delta={ma-mb:+.0f}")

if __name__ == "__main__":
    main()
