"""Role-fit scoring against named target profiles.

A profile is a weighted list of metrics, defined in `feature_config.yml` under
`scouting_profiles`. The fit score is the weighted mean of a player's
within-role percentiles on those metrics, scaled 0-100. Metrics a player has no
value for are skipped and the weights renormalised, but a player must cover at
least `min_coverage` of the profile's weight or no score is given.

The score is descriptive: it says how strongly a player's numbers match the
profile, not how good they are or how they would fit a system.
"""

from __future__ import annotations

import pandas as pd


def profiles_for_role(config: dict, role: str) -> dict[str, dict[str, float]]:
    """Named profiles available for a role: {profile name: {metric: weight}}."""
    return {
        name: spec["metrics"]
        for name, spec in config.get("scouting_profiles", {}).get(role, {}).items()
    }


def score_profile(
    season: pd.DataFrame, weights: dict[str, float], min_coverage: float = 0.7
) -> pd.DataFrame:
    """Fit score (0-100) per player, plus each metric's contribution.

    Returns a frame indexed like `season` with `fit_score` and one
    `contrib_<metric>` column per metric (points of the score it supplied).
    """
    cols = [f"pct_{m}" for m in weights]
    w = pd.Series(list(weights.values()), index=cols, dtype=float)
    pct = season[cols]
    used_weight = pct.notna().mul(w, axis=1).sum(axis=1)
    coverage = used_weight / w.sum()
    weighted = pct.fillna(0).mul(w, axis=1)
    denominator = used_weight.where(used_weight > 0)
    score = (weighted.sum(axis=1) / denominator * 100).where(coverage >= min_coverage)

    out = pd.DataFrame({"fit_score": score}, index=season.index)
    for metric, col in zip(weights, cols, strict=True):
        out[f"contrib_{metric}"] = weighted[col] / denominator * 100
    return out


def top_drivers(row: pd.Series, weights: dict[str, float], n: int = 3) -> list[str]:
    """The metrics that supplied most of one player's fit score."""
    contrib = pd.Series({m: row.get(f"contrib_{m}") for m in weights}).dropna()
    return contrib.sort_values(ascending=False).head(n).index.tolist()
