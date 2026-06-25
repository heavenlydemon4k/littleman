"""EXPOSURE.md — a deterministically rendered risk map.

Unlike the agent-authored construct docs (PRIORITIES/SELF/CALENDAR), EXPOSURE.md is drawn
straight from the world model each wake by a pure formatter — no LLM. Risk figures must be
exact, so the model never authors them; it reads this doc in-prompt and reasons over it during
the directive/strategy step. See docs/ROADMAP.md item #1.
"""

from __future__ import annotations

from typing import Any


def _money(v: Any) -> str:
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def render_exposure(ws: dict[str, Any]) -> str:
    """Render EXPOSURE.md markdown from a world-model snapshot dict.

    Tolerant of a partial snapshot: any missing field is treated as zero/empty, so callers
    that pass a lightweight dict still get a valid (if sparse) document.
    """
    balance = _num(ws.get("wallet_balance_usdc"))
    available = _num(ws.get("available_balance_usdc"))
    pnl = _num(ws.get("total_pnl"))
    peak = _num(ws.get("peak_balance"), balance)
    open_positions = ws.get("open_positions") or []
    pending = ws.get("pending_resolutions") or []

    # Exposure: prefer a precomputed total, else sum position sizes.
    exposure = ws.get("open_exposure_usdc")
    if exposure is None:
        exposure = sum(_num(p.get("size_usdc")) for p in open_positions)
    exposure = _num(exposure)

    by_cat = ws.get("exposure_by_category") or {}

    # Drawdown from peak (always >= 0).
    drawdown = max(0.0, peak - balance)
    drawdown_pct = (drawdown / peak * 100.0) if peak > 0 else 0.0
    deployed_pct = (exposure / balance * 100.0) if balance > 0 else 0.0

    breaker = bool(ws.get("circuit_breaker_active"))
    pnl_sign = "+" if pnl >= 0 else "-"

    lines: list[str] = [
        "# EXPOSURE.md — risk map",
        "",
        "_Rendered from the world model each wake. Read-only; do not edit — your changes are overwritten._",
        "",
        "## Capital",
        f"- Wallet balance: {_money(balance)}",
        f"- Available (uncommitted): {_money(available)}",
        f"- Total PnL: {pnl_sign}{_money(abs(pnl))}",
        "",
        "## Exposure",
        f"- Open exposure: {_money(exposure)} ({deployed_pct:.0f}% of balance deployed)",
        f"- Open positions: {len(open_positions)}",
        f"- Pending resolution: {len(pending)}",
    ]

    if by_cat:
        lines.append("- By category:")
        for cat, amt in sorted(by_cat.items(), key=lambda kv: -_num(kv[1])):
            lines.append(f"  - {cat}: {_money(amt)}")

    lines += [
        "",
        "## Drawdown",
        f"- Peak balance: {_money(peak)}",
        f"- Current drawdown: {_money(drawdown)} ({drawdown_pct:.1f}% from peak)",
        f"- Circuit breaker: {'⚠️ ACTIVE — halt new risk' if breaker else 'inactive'}",
    ]

    if open_positions:
        lines += ["", "## Open positions"]
        for p in open_positions:
            title = p.get("market_title") or p.get("market_id") or "unknown market"
            direction = p.get("direction") or "?"
            size = _money(p.get("size_usdc"))
            entry = _num(p.get("entry_price"))
            ppnl = p.get("pnl")
            pnl_str = f", PnL {('+' if _num(ppnl) >= 0 else '-')}{_money(abs(_num(ppnl)))}" if ppnl is not None else ""
            lines.append(f"- {title} — {direction} {size} @ {entry:.2f}{pnl_str}")

    return "\n".join(lines) + "\n"
