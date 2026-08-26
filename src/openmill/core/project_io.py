"""Versioned JSON persistence for portable machining projects."""

from __future__ import annotations

import json
from pathlib import Path

from openmill.core.models import Project


def dumps_project(project: Project) -> str:
    return json.dumps(project.to_dict(), ensure_ascii=False, indent=2) + "\n"


def loads_project(content: str) -> Project:
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("Le projet doit contenir un objet JSON.")
    return Project.from_dict(payload)


def load_project(path: str | Path) -> Project:
    return loads_project(Path(path).read_text(encoding="utf-8"))


def save_project(project: Project, path: str | Path) -> None:
    Path(path).write_text(dumps_project(project), encoding="utf-8")

