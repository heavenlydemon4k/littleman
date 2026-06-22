from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class TaskType(str, Enum):
    RESEARCH = "RESEARCH"
    ANALYSIS = "ANALYSIS"
    DECISION = "DECISION"
    MONITOR = "MONITOR"
    RESOLVE = "RESOLVE"
    EXECUTE = "EXECUTE"


@dataclass
class TaskNode:
    id: str
    type: TaskType
    title: str
    params: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None

    def is_ready(self, done_ids: set[str]) -> bool:
        return self.status == TaskStatus.PENDING and all(d in done_ids for d in self.depends_on)


class TaskTree:
    def __init__(self):
        self._nodes: dict[str, TaskNode] = {}
        self._title_to_id: dict[str, str] = {}

    def add(
        self,
        task_type: str | TaskType,
        title: str,
        params: dict[str, Any],
        depends_on: list[str] | None = None,
    ) -> TaskNode:
        task_id = str(uuid.uuid4())
        dep_ids: list[str] = []
        for dep_title in (depends_on or []):
            if dep_title in self._title_to_id:
                dep_ids.append(self._title_to_id[dep_title])

        node = TaskNode(
            id=task_id,
            type=TaskType(task_type) if isinstance(task_type, str) else task_type,
            title=title,
            params=params,
            depends_on=dep_ids,
        )
        self._nodes[task_id] = node
        self._title_to_id[title] = task_id
        return node

    def get_ready(self) -> list[TaskNode]:
        done_ids = {n.id for n in self._nodes.values() if n.status == TaskStatus.DONE}
        return [n for n in self._nodes.values() if n.is_ready(done_ids)]

    def mark_running(self, task_id: str) -> None:
        self._nodes[task_id].status = TaskStatus.RUNNING

    def mark_done(self, task_id: str, result: Any = None) -> None:
        self._nodes[task_id].status = TaskStatus.DONE
        self._nodes[task_id].result = result

    def mark_failed(self, task_id: str, error: str) -> None:
        self._nodes[task_id].status = TaskStatus.FAILED
        self._nodes[task_id].error = error

    def mark_skipped(self, task_id: str) -> None:
        self._nodes[task_id].status = TaskStatus.SKIPPED

    def is_complete(self) -> bool:
        return all(
            n.status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.SKIPPED)
            for n in self._nodes.values()
        )

    def result_for(self, title: str) -> Any:
        task_id = self._title_to_id.get(title)
        if task_id and task_id in self._nodes:
            return self._nodes[task_id].result
        return None

    def summary(self) -> dict[str, Any]:
        counts = {s: 0 for s in TaskStatus}
        for n in self._nodes.values():
            counts[n.status] += 1
        return {
            "total": len(self._nodes),
            "done": counts[TaskStatus.DONE],
            "failed": counts[TaskStatus.FAILED],
            "skipped": counts[TaskStatus.SKIPPED],
            "pending": counts[TaskStatus.PENDING],
            "tasks": [
                {
                    "title": n.title,
                    "type": n.type,
                    "status": n.status,
                    "error": n.error,
                }
                for n in self._nodes.values()
            ],
        }

    @classmethod
    def from_specs(cls, specs: list[dict[str, Any]]) -> "TaskTree":
        tree = cls()
        for spec in specs:
            tree.add(
                task_type=spec["type"],
                title=spec["title"],
                params=spec.get("params", {}),
                depends_on=spec.get("depends_on", []),
            )
        return tree
