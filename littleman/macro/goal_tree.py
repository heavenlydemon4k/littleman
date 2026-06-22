import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from littleman.db.models import Strategy


async def get_or_create_root(db: AsyncSession) -> Strategy:
    result = await db.execute(
        select(Strategy).where(Strategy.parent_id == None, Strategy.node_type == "GOAL")
    )
    root = result.scalar_one_or_none()
    if root:
        return root

    root = Strategy(
        id=str(uuid.uuid4()),
        node_type="GOAL",
        title="Maximize risk-adjusted return on Polymarket budget",
        rationale="Core objective: compound USDC balance through prediction market edge",
        status="ACTIVE",
        metadata_={},
    )
    db.add(root)
    await db.commit()
    await db.refresh(root)
    return root


async def get_active_strategies(db: AsyncSession) -> list[Strategy]:
    result = await db.execute(
        select(Strategy).where(
            Strategy.status == "ACTIVE",
            Strategy.node_type == "STRATEGY",
        )
    )
    return list(result.scalars().all())


async def create_node(
    db: AsyncSession,
    node_type: str,
    title: str,
    rationale: str | None = None,
    parent_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Strategy:
    if parent_id is None:
        root = await get_or_create_root(db)
        parent_id = root.id

    node = Strategy(
        id=str(uuid.uuid4()),
        parent_id=parent_id,
        node_type=node_type,
        title=title,
        rationale=rationale,
        status="ACTIVE",
        metadata_=metadata or {},
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node


async def update_status(db: AsyncSession, node_id: str, status: str) -> Strategy | None:
    result = await db.execute(select(Strategy).where(Strategy.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        return None
    node.status = status
    await db.commit()
    return node


async def add_note(db: AsyncSession, node_id: str, note: str) -> Strategy | None:
    result = await db.execute(select(Strategy).where(Strategy.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        return None
    notes = node.metadata_.get("notes", []) if node.metadata_ else []
    notes.append(note)
    node.metadata_ = {**(node.metadata_ or {}), "notes": notes}
    await db.commit()
    return node


async def get_tree_as_dict(db: AsyncSession) -> dict:
    result = await db.execute(select(Strategy).order_by(Strategy.created_at))
    all_nodes = result.scalars().all()

    nodes_by_id: dict[str, dict] = {}
    for n in all_nodes:
        nodes_by_id[n.id] = {
            "id": n.id,
            "type": n.node_type,
            "title": n.title,
            "rationale": n.rationale,
            "status": n.status,
            "notes": (n.metadata_ or {}).get("notes", []),
            "children": [],
        }

    root_nodes = []
    for n in all_nodes:
        node_dict = nodes_by_id[n.id]
        if n.parent_id and n.parent_id in nodes_by_id:
            nodes_by_id[n.parent_id]["children"].append(node_dict)
        elif n.parent_id is None:
            root_nodes.append(node_dict)

    return {"roots": root_nodes} if root_nodes else {"roots": [], "nodes": list(nodes_by_id.values())}
