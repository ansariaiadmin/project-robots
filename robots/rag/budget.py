"""Budget — strict token allocator (size//4, first vs on-demand)."""

from __future__ import annotations


def allocate(ranked: list[dict], budget: int) -> tuple[list[dict], list[dict], int]:
    """Split ranked chunks into (first, on_demand, estimated_first_tokens).

    Mirrors context_robot: the first chunk is always 'first' (even if it alone
    exceeds budget); subsequent chunks go on-demand once budget is exceeded.
    Each item must carry 'token_est'.
    """
    first: list[dict] = []
    on_demand: list[dict] = []
    estimated = 0
    for item in ranked:
        tokens = int(item.get("token_est", 1))
        if first and estimated + tokens > budget:
            on_demand.append({**item, "open": "on-demand"})
            continue
        estimated += tokens
        first.append({**item, "open": "first"})
    return first, on_demand, estimated
