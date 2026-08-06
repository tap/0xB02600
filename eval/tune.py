"""Parallel tuning harness for bot2.py constants.

For each variant (one constant changed from baseline), plays MATCHES_PER
games of [variant, baseline bot2, bot.py, random] with rotated seats, then
reports the variant's win rate and mean halite alongside the baseline's
in the very same games (paired comparison cancels a lot of match noise).
"""
import re
import sys
import json
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

SCRATCH = Path("/tmp/claude-0/-home-user-0xB02600/cdfda1a8-9935-514b-a0c4-fcc97f43fd4d/scratchpad")
KAGGLE = SCRATCH / "hackathon/hackathon/kaggle-environments"
BOT2 = Path("/home/user/0xB02600/bot2.py")
BOT1 = Path("/home/user/0xB02600/bot.py")
VARIANT_DIR = SCRATCH / "variants"
VARIANT_DIR.mkdir(exist_ok=True)

MATCHES_PER = 6
WORKERS = 4

SWEEPS = {
    "FLEET_CAP_EARLY": [18, 32],
    "HUNT_WEIGHT": [0.0, 0.35, 1.2],
    "CARGO_RETURN_THRESHOLD": [350, 700],
    "HUNTERS_PER_PREY": [1, 3],
    "SPAWN_STOP_STEPS_LEFT": [50, 100],
}


def make_variant(name, value):
    src = BOT2.read_text()
    pattern = rf"^{name} = [^ ]+"
    new_src, n = re.subn(pattern, f"{name} = {value}", src, count=1, flags=re.M)
    assert n == 1, f"constant {name} not found"
    path = VARIANT_DIR / f"{name}_{str(value).replace('.', 'p')}.py"
    path.write_text(new_src)
    return path


def play(variant_path, rotation):
    sys.path.insert(0, str(KAGGLE))
    from kaggle_environments import make

    agents = [str(variant_path), str(BOT2), str(BOT1), "random"]
    seated = agents[rotation:] + agents[:rotation]
    env = make("halite")
    env.run(seated)
    final = env.steps[-1]
    out = {}
    variant_labeled = False
    for seat, agent in enumerate(seated):
        if agent == str(variant_path) and not variant_labeled:
            label = "variant"
            variant_labeled = True
        else:
            label = Path(agent).name if agent != "random" else "random"
        out[label] = {
            "reward": final[seat].reward,
            "status": str(final[seat].status),
        }
    return out


def main():
    jobs = []
    for name, values in SWEEPS.items():
        for value in values:
            path = make_variant(name, value)
            for m in range(MATCHES_PER):
                jobs.append((f"{name}={value}", path, m % 4))
    # Baseline-vs-baseline control games to gauge noise.
    for m in range(MATCHES_PER):
        jobs.append(("BASELINE(control)", BOT2, m % 4))

    results = {}
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        futures = {
            pool.submit(play, path, rot): key for key, path, rot in jobs
        }
        done = 0
        for fut in as_completed(futures):
            key = futures[fut]
            try:
                results.setdefault(key, []).append(fut.result())
            except Exception as e:
                results.setdefault(key, []).append({"error": str(e)})
            done += 1
            print(f"[{done}/{len(jobs)}] {key}", file=sys.stderr, flush=True)

    (SCRATCH / "tune_results.json").write_text(json.dumps(results, indent=1))

    print(f"\n{'variant':34s} {'v_win':>5s} {'v_mean':>8s} {'base_mean':>9s} {'delta':>8s}")
    for key in sorted(results):
        games = [g for g in results[key] if "error" not in g]
        if not games:
            print(f"{key:34s}  ALL ERRORED")
            continue
        v = [g["variant"]["reward"] or 0 for g in games]
        b = [g.get("bot2.py", {}).get("reward") or 0 for g in games]
        wins = sum(
            1 for g in games
            if (g["variant"]["reward"] or 0)
            == max((p["reward"] or 0) for p in g.values())
        )
        vm, bm = sum(v) / len(v), sum(b) / len(b)
        print(f"{key:34s} {wins}/{len(games)} {vm:8.0f} {bm:9.0f} {vm - bm:+8.0f}")


if __name__ == "__main__":
    main()
