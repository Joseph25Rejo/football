"""Target lists for a club: outside players who could fill a gap.

Two entry points, both excluding the club's own players and both descriptive:

* `role_targets`   - candidates for a position, ranked by role rating or by a
                     named profile, shown against the club's weakest starter.
* `weakness_targets` - candidates for a weak team statistic, using the
                     config's `team_weakness_targets` judgement on which roles
                     and player metrics address it.

Neither says a player would improve the team. They say whose numbers point the
right way.
"""

from __future__ import annotations

import pandas as pd

from .diagnosis import role_rating, strengths
from .profiles import profiles_for_role, score_profile, top_drivers


def _weakest_starter_rating(rated: pd.DataFrame, team_id: int, role: str, n: int) -> float:
    club = rated[(rated["team_id"] == team_id) & (rated["role"] == role)]
    starters = club.dropna(subset=["rating"]).nlargest(n, "minutes")
    return float(starters["rating"].min()) if not starters.empty else float("nan")


def role_targets(
    players: pd.DataFrame,
    config: dict,
    team_id: int,
    role: str,
    profile_key: str | None = None,
    min_minutes: float = 900,
    limit: int = 25,
) -> tuple[pd.DataFrame, float]:
    """Outside candidates for a role, plus the club's weakest-starter rating.

    `score` is the role rating, or the named profile's fit if `profile_key` is
    given. `vs_weakest` is the candidate's role rating minus the club's weakest
    starter's, so a positive number means they rate above the player they might
    replace.
    """
    rated = players.copy()
    rated["rating"] = role_rating(rated, config)
    n = config["club_diagnosis"]["starters_per_role"][role]
    weakest = _weakest_starter_rating(rated, team_id, role, n)

    pool = rated[(rated["role"] == role) & (rated["team_id"] != team_id)
                 & (rated["minutes"] >= min_minutes)].copy()
    if profile_key:
        weights = profiles_for_role(config, role)[profile_key]
        scored = score_profile(pool, weights, config["similarity"]["min_feature_coverage"])
        pool = pool.join(scored)
        pool["score"] = pool["fit_score"]
        pool["why"] = pool.apply(lambda r: top_drivers(r, weights), axis=1)
    else:
        pool["score"] = pool["rating"]
        pool["why"] = pool.apply(lambda r: strengths(r, config), axis=1)
    pool["vs_weakest"] = pool["rating"] - weakest
    pool = pool.dropna(subset=["score"]).sort_values("score", ascending=False)
    return pool.head(limit).reset_index(drop=True), weakest


def weakness_targets(
    players: pd.DataFrame,
    config: dict,
    team_id: int,
    metric: str,
    min_minutes: float = 900,
    limit: int = 25,
) -> pd.DataFrame:
    """Outside candidates for a weak team metric, across the roles that address it.

    `score` is the equal-weight mean percentile on the mapped player metrics,
    within the candidate's own role, scaled 0-100.
    """
    mapping = config["team_weakness_targets"].get(metric)
    if mapping is None:
        raise KeyError(f"no player mapping for team metric: {metric}")
    weights = dict.fromkeys(mapping["player_metrics"], 1.0)

    pool = players[players["role"].isin(mapping["roles"])
                   & (players["team_id"] != team_id)
                   & (players["minutes"] >= min_minutes)].copy()
    scored = score_profile(pool, weights, config["similarity"]["min_feature_coverage"])
    pool = pool.join(scored)
    pool["score"] = pool["fit_score"]
    pool["why"] = pool.apply(lambda r: top_drivers(r, weights, n=len(weights)), axis=1)
    pool = pool.dropna(subset=["score"]).sort_values("score", ascending=False)
    return pool.head(limit).reset_index(drop=True)
