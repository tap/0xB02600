# X + pacifist + pacifist + turtle : does X suppress a runaway economy?
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
KAGGLE = "hackathon/hackathon/kaggle-environments"
S = "/tmp/claude-0/-home-user-0xB02600/cdfda1a8-9935-514b-a0c4-fcc97f43fd4d/scratchpad"
X = sys.argv[1]
FIELD = [f"{S}/corpus/pacifist.py", f"{S}/corpus/pacifist.py", f"{S}/corpus/turtle.py"]
N = 8
def play(rot):
    sys.path.insert(0, KAGGLE)
    from kaggle_environments import make
    agents = [X] + FIELD
    seated = agents[rot:] + agents[:rot]
    env = make("halite"); env.run(seated)
    final = env.steps[-1]
    xi = seated.index(X)
    rewards = [s.reward if s.reward is not None else -9999 for s in final]
    rank = 1 + sum(1 for j, r in enumerate(rewards) if j != xi and r > rewards[xi])
    return rewards[xi], rank
res = []
with ProcessPoolExecutor(max_workers=4) as pool:
    for f in as_completed([pool.submit(play, m % 4) for m in range(N)]):
        res.append(f.result())
wins = sum(1 for _, rk in res if rk == 1)
mh = sum(r for r, _ in res)/len(res)
mr = sum(rk for _, rk in res)/len(res)
print(f"{Path(X).name:16s} wins {wins}/{N}  mean_rank {mr:.2f}  mean_halite {mh:.0f}")
