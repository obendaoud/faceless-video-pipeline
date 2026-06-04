"""Pipeline state machine — tracks progress, enables resume after crash."""

import json
import os
from datetime import datetime, timezone


STAGES = [
    "research",
    "script",
    "images",
    "audio",
    "captions",
    "assembly",
    "upload",
]


def init_state(project_dir: str, topic: str, niche: str) -> dict:
    state = {
        "topic": topic,
        "niche": niche,
        "project_dir": project_dir,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "stages": {stage: {"status": "pending"} for stage in STAGES},
        "artifacts": {},
    }
    save_state(state, project_dir)
    return state


def load_state(project_dir: str) -> dict | None:
    path = os.path.join(project_dir, "state.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict, project_dir: str) -> None:
    os.makedirs(project_dir, exist_ok=True)
    path = os.path.join(project_dir, "state.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def start_stage(state: dict, stage: str) -> dict:
    state["stages"][stage] = {
        "status": "in_progress",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    save_state(state, state["project_dir"])
    return state


def complete_stage(state: dict, stage: str, artifacts: dict | None = None) -> dict:
    state["stages"][stage]["status"] = "completed"
    state["stages"][stage]["completed_at"] = datetime.now(timezone.utc).isoformat()
    if artifacts:
        state["artifacts"].update(artifacts)
    save_state(state, state["project_dir"])
    return state


def fail_stage(state: dict, stage: str, error: str) -> dict:
    state["stages"][stage]["status"] = "failed"
    state["stages"][stage]["error"] = error
    state["stages"][stage]["failed_at"] = datetime.now(timezone.utc).isoformat()
    save_state(state, state["project_dir"])
    return state


def get_resume_stage(state: dict) -> str | None:
    for stage in STAGES:
        status = state["stages"][stage]["status"]
        if status in ("pending", "failed", "in_progress"):
            return stage
    return None


def is_stage_done(state: dict, stage: str) -> bool:
    return state["stages"][stage]["status"] == "completed"
