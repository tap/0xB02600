import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
KAGGLE = "hackathon/hackathon/kaggle-environments"
REPO = "/home/user/0xB02600"
S = "/tmp/claude-0/-home-user-0xB02600/cdfda1a8-9935-514b-a0c4-fcc97f43fd4d/scratchpad"
AGENTS = [f"{S}/corpus/colton.py", f"{S}/corpus/gavin_v2_clean.py",
          f"{S}/corpus/pacifist.py", f"{REPO}/bot2.py"]
NAMES = ["colton", "gavin", "pacifist", "bot2"]
N = 12
def play(rot):
    sys.path.insert(0, KAGGLE)
    from kaggle_environments import make
    order = list(range(4))[rot:] + list(range(4))[:rot]
    seated = [AGENTS[i] for i in order]
    env = make("halite")
    env.run(seated)
    final = env.steps[-1]
    return {NAMES[i]: (final[seat].reward if final[seat].reward is not None else -9999)
            for seat, i in enumerate(order)}
results = []
with ProcessPoolExecutor(max_workers=4) as pool:
    futs = [pool.submit(play, m % 4) for m in range(N)]
    for f in as_completed(futs):
        results.append(f.result())
wins = {n: 0 for n in NAMES}; ranks = {n: [] for n in NAMES}
for g in results:
    order = sorted(NAMES, key=lambda n: -g[n])
    wins[order[0]] += 1
    for rk, n in enumerate(order, 1): ranks[n].append(rk)
print(f"{'bot':10s} {'wins':>5s} {'mean_rank':>9s} {'mean_halite':>11s}")
for n in sorted(NAMES, key=lambda n: sum(ranks[n])/len(ranks[n])):
    mh = sum(g[n] for g in results)/len(results)
    print(f"{n:10s} {wins[n]:5d} {sum(ranks[n])/len(ranks[n]):9.2f} {mh:11.0f}")
