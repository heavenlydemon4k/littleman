"""Strategy planner — directive -> goal-tree mutations + task specs.

Reads the directive and the current goal tree, produces strategy changes and a concrete task
plan. Applies the goal-tree mutations and returns task specs for the task layer.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from littleman.llm.complete import complete_json
from littleman.llm.prompts import STRATEGY_SYSTEM, agent_description, render
from littleman.macro import goal_tree
from littleman.skills.registry import get_registry


async def plan(db: AsyncSession, directive: dict[str, Any]) -> dict[str, Any]:
    await goal_tree.get_or_create_root(db)
    tree = await goal_tree.get_tree_as_dict(db)
    registry = get_registry()

    system = render(
        STRATEGY_SYSTEM,
        skills_summary=registry.summary_text(),
        directive_json=json.dumps(directive, indent=2),
        goal_tree_json=json.dumps(tree, indent=2),
        agent_description=agent_description(),
    )
    result = await complete_json(system, "Produce the plan now.", tier="primary")

    mutations = result.get("goal_tree_mutations", [])
    await _apply_mutations(db, mutations)

    return {"tasks": result.get("tasks", []), "mutations_applied": len(mutations)}


async def _apply_mutations(db: AsyncSession, mutations: list[dict[str, Any]]) -> None:
    for m in mutations:
        action = m.get("action")
        if action == "create":
            await goal_tree.create_node(
                db,
                node_type=m.get("node_type", "STRATEGY"),
                title=m["title"],
                rationale=m.get("rationale"),
                parent_id=m.get("parent_id"),
            )
        elif action == "update_status" and m.get("node_id"):
            await goal_tree.update_status(db, m["node_id"], m.get("new_status", "ACTIVE"))
        elif action == "add_note" and m.get("node_id"):
            await goal_tree.add_note(db, m["node_id"], m.get("rationale") or m.get("title", ""))
