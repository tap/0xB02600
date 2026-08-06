import sys
sys.path.insert(0, "/tmp/claude-0/-home-user-0xB02600/cdfda1a8-9935-514b-a0c4-fcc97f43fd4d/scratchpad/hackathon/hackathon/kaggle-environments")
from kaggle_environments import make

agent_path = sys.argv[1]
name = agent_path.split("/")[-1]
env = make("halite", debug=True)
env.run([agent_path, "random", "random", "random"])

prev_ships = None
for step_idx, step in enumerate(env.steps):
    obs = step[0].observation
    halite, shipyards, ships = obs.players[0]
    n_ships, n_yards = len(ships), len(shipyards)
    if prev_ships is None or n_ships != prev_ships[0] or n_yards != prev_ships[1]:
        cargo = sum(s[1] for s in ships.values())
        print(f"step {step_idx:3d}: bank={halite:6d} ships={n_ships:2d} yards={n_yards} cargo={cargo}")
    prev_ships = (n_ships, n_yards)

final = env.steps[-1]
print(f"\nFINAL {name}: reward={final[0].reward} status={final[0].status}")
print("others:", [(s.reward, s.status) for s in final[1:]])
