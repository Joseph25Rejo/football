"""Criteria search: filter players by role, minutes, club and percentile floors.

Pure functions over the player-season frame, with no Streamlit import, so the
logic is testable on its own. Percentiles are the within-role ranks already in
`mart_player_season` (columns `pct_<metric>`, 0-1).
"""

from __future__ import annotations

import pandas as pd


def filter_players(
    season: pd.DataFrame,
    role: str | None = None,
    min_minutes: float = 0.0,
    thresholds: dict[str, float] | None = None,
    team_ids: list[int] | None = None,
    exclude_team_ids: list[int] | None = None,
) -> pd.DataFrame:
    """Players meeting every criterion, strongest on the thresholds first.

    `thresholds` maps a metric column (e.g. "prog_passes_p90") to a minimum
    within-role percentile in 0-1. A player with no value for a thresholded
    metric is excluded: missing data cannot be said to pass.
    """
    thresholds = thresholds or {}
    mask = season["minutes"] >= min_minutes
    if role:
        mask &= season["role"] == role
    if team_ids:
        mask &= season["team_id"].isin(team_ids)
    if exclude_team_ids:
        mask &= ~season["team_id"].isin(exclude_team_ids)
    for metric, floor in thresholds.items():
        column = f"pct_{metric}"
        if column not in season.columns:
            raise KeyError(f"unknown metric: {metric}")
        mask &= season[column] >= floor

    result = season[mask].copy()
    if thresholds:
        cols = [f"pct_{m}" for m in thresholds]
        result["criteria_score"] = result[cols].mean(axis=1)
        result = result.sort_values("criteria_score", ascending=False)
    else:
        result = result.sort_values("minutes", ascending=False)
    return result.reset_index(drop=True)
