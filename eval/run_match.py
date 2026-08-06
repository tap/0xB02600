import sys, json
sys.path.insert(0, "/tmp/claude-0/-home-user-0xB02600/cdfda1a8-9935-514b-a0c4-fcc97f43fd4d/scratchpad/hackathon/hackathon/kaggle-environments")
from kaggle_environments import make

agents = sys.argv[1:5]
env = make("halite", debug=True)
env.run(agents)
final = env.steps[-1]
rewards = [s["reward"] for s in final]
statuses = [s["status"] for s in final]
names = [a.split("/")[-1] for a in agents]
order = sorted(range(4), key=lambda i: (rewards[i] if rewards[i] is not None else -1), reverse=True)
for rank, i in enumerate(order, 1):
    print(f"{rank}. {names[i]:12s} halite={rewards[i]} status={statuses[i]}")
