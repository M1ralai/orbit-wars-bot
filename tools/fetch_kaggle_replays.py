import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COMPETITION = "orbit-wars"
DEFAULT_SUBMISSION_ID = "52865334"


def default_kaggle_bin():
    local_bin = REPO_ROOT / ".venv" / "bin" / "kaggle"
    if local_bin.exists():
        return str(local_bin)
    return os.environ.get("KAGGLE_BIN", "kaggle")


def run_kaggle(kaggle_bin, args, check=True):
    command = [kaggle_bin, *args]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
    )

    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"{' '.join(command)} failed: {message}")

    return result


def parse_episode_csv(output):
    lines = []
    for line in output.splitlines():
        if not line.strip():
            break
        if line.startswith("Use "):
            break
        lines.append(line)

    if not lines:
        return []

    return list(csv.DictReader(lines))


def list_episodes(kaggle_bin, submission_id):
    result = run_kaggle(
        kaggle_bin,
        ["competitions", "episodes", str(submission_id), "-v"],
    )
    return parse_episode_csv(result.stdout)


def latest_submission_id(kaggle_bin, competition):
    result = run_kaggle(
        kaggle_bin,
        ["competitions", "submissions", competition, "-v"],
    )
    rows = list(csv.DictReader(result.stdout.splitlines()))
    complete_rows = [row for row in rows if row.get("status", "").endswith("COMPLETE")]
    selected = complete_rows[0] if complete_rows else rows[0] if rows else None
    if not selected:
        raise SystemExit(f"no submissions found for {competition}")
    return selected["ref"]


def replay_path(replay_dir, episode_id):
    return replay_dir / f"episode-{episode_id}-replay.json"


def log_path(log_dir, episode_id, agent_index):
    return log_dir / f"episode-{episode_id}-agent-{agent_index}-logs.json"


def download_replay(kaggle_bin, episode_id, replay_dir, force):
    path = replay_path(replay_dir, episode_id)
    if path.exists() and not force:
        return {"path": str(path), "status": "exists"}

    result = run_kaggle(
        kaggle_bin,
        ["competitions", "replay", str(episode_id), "-p", str(replay_dir)],
        check=False,
    )
    if result.returncode != 0:
        return {
            "path": str(path),
            "status": "error",
            "message": (result.stderr or result.stdout).strip(),
        }
    return {"path": str(path), "status": "downloaded"}


def download_logs(kaggle_bin, episode_id, log_dir, max_agents, force):
    records = []
    for agent_index in range(max_agents):
        path = log_path(log_dir, episode_id, agent_index)
        if path.exists() and not force:
            records.append(
                {"agent_index": agent_index, "path": str(path), "status": "exists"}
            )
            continue

        result = run_kaggle(
            kaggle_bin,
            [
                "competitions",
                "logs",
                str(episode_id),
                str(agent_index),
                "-p",
                str(log_dir),
            ],
            check=False,
        )
        message = (result.stderr or result.stdout).strip()

        if result.returncode == 0:
            status = "downloaded"
        elif "403" in message or "Forbidden" in message:
            status = "forbidden"
        else:
            status = "error"

        records.append(
            {
                "agent_index": agent_index,
                "path": str(path),
                "status": status,
                "message": message if status != "downloaded" else "",
            }
        )

    return records


def write_manifest(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--competition", default=DEFAULT_COMPETITION)
    parser.add_argument("--submission-id", default=DEFAULT_SUBMISSION_ID)
    parser.add_argument("--replay-dir", type=Path, default=Path("replays"))
    parser.add_argument("--log-dir", type=Path, default=Path("logs"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("replays/v0_1_manifest.json"),
    )
    parser.add_argument("--kaggle-bin", default=default_kaggle_bin())
    parser.add_argument("--max-agents", type=int, default=4)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-logs", action="store_true")
    parser.add_argument("--include-incomplete", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    submission_id = args.submission_id
    if str(submission_id).lower() == "latest":
        submission_id = latest_submission_id(args.kaggle_bin, args.competition)

    replay_dir = REPO_ROOT / args.replay_dir
    log_dir = REPO_ROOT / args.log_dir
    replay_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    episodes = list_episodes(args.kaggle_bin, submission_id)
    fetched = []

    for episode in episodes:
        episode_id = episode.get("id")
        state = episode.get("state", "")
        if not episode_id:
            continue
        if not args.include_incomplete and not state.endswith("COMPLETED"):
            continue

        replay_record = download_replay(
            args.kaggle_bin,
            episode_id,
            replay_dir,
            args.force,
        )
        log_records = []
        if not args.skip_logs:
            log_records = download_logs(
                args.kaggle_bin,
                episode_id,
                log_dir,
                args.max_agents,
                args.force,
            )

        fetched.append(
            {
                "episode": episode,
                "replay": replay_record,
                "logs": log_records,
            }
        )

    payload = {
        "competition": args.competition,
        "submission_id": str(submission_id),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "episodes": fetched,
    }
    write_manifest(REPO_ROOT / args.manifest, payload)

    print(
        json.dumps(
            {
                "submission_id": str(args.submission_id),
                "resolved_submission_id": str(submission_id),
                "episodes": len(fetched),
                "manifest": str(REPO_ROOT / args.manifest),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
