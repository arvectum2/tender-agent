"""Evidence-first procurement market intelligence (offline/read-only boundary)."""

from .service import MarketInputError, analyze_market, render_markdown

__all__ = ["MarketInputError", "analyze_market", "render_markdown"]
