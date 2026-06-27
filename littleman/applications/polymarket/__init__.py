"""Polymarket prediction-market trading application for the littleman platform."""

from littleman.applications import register_builtin
from littleman.applications.polymarket.app import PolymarketApplication

register_builtin("Polymarket trading", lambda: PolymarketApplication())

__all__ = ["PolymarketApplication"]
