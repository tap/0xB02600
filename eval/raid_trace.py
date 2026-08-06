import sys
sys.path.insert(0, "hackathon/hackathon/kaggle-environments")
from kaggle_environments import make

# 2-player: raider (seat 0) vs bot2 (seat 1). Cleanest test of the attack.
env = make("halite", debug=True, configuration={"agentExec": "LOCAL"})
env.run(["corpus/raider.py", "/home/user/0xB02600/bot2.py"])

prev = None
for i, step in enumerate(env.steps):
    obs = step[0].observation
    r_h, r_yards, r_ships = obs.players[0]
    b_h, b_yards, b_ships = obs.players[1]
    shields = obs.get("shipyardShields", {})
    b_shield_total = sum(shields.get(sid, 3) for sid in b_yards)
    key = (len(r_ships), len(r_yards), len(b_ships), len(b_yards), b_shield_total)
    if prev != key and i % 1 == 0:
        if prev is None or key[3] != prev[3] or key[4] != prev[4] or i % 40 == 0:
            print(f"step {i:3d}: raider[ships={len(r_ships):2d} yards={len(r_yards)}] "
                  f"bot2[ships={len(b_ships):2d} yards={len(b_yards)} shields={b_shield_total} bank={b_h}]")
    prev = key

final = env.steps[-1]
print(f"\nFINAL raider={final[0].reward} ({final[0].status})  bot2={final[1].reward} ({final[1].status})")
