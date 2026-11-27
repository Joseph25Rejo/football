"""Club diagnosis: what a squad is made of, and where it is strong or thin.

Everything here is descriptive and built on within-role percentiles from
`mart_player_season`. A player's *rating* is the weighted mean of their
percentiles on the features the config lists for their role (the same weights
the similarity engine uses), scaled 0-100. It says how strongly a player's
numbers stand out for their role in this league and season, not how good they
are.
"""

from __future__ import annotations

import pandas as pd

from ..app.labels import NOT_A_DISTINCTION
from .profiles import profiles_for_role, score_profile


def _creditable(weights: dict[str, float]) -> dict[str, float]:
    """Drop metrics where a high percentile describes rather than distinguishes.

    A top-percentile turnover rate is not a strength, so it must neither raise a
    rating nor be listed as something a player is good at.
    """
    return {m: w for m, w in weights.items() if m not in NOT_A_DISTINCTION}


def role_rating(players: pd.DataFrame, config: dict) -> pd.Series:
    """Rating (0-100) per player, using their own role's feature weights."""
    ratings = pd.Series(index=players.index, dtype=float)
    for role, weights in config["role_features"].items():
        mask = players["role"] == role
        if mask.any():
            scored = score_profile(
                players[mask], _creditable(weights), config["similarity"]["min_feature_coverage"])
            ratings[mask] = scored["fit_score"]
    return ratings


def best_profile(row: pd.DataFrame, config: dict) -> tuple[str | None, float | None]:
    """The target profile a single-row frame fits best, as (label, fit score)."""
    role = row["role"].iloc[0]
    best: tuple[str | None, float | None] = (None, None)
    for key, weights in profiles_for_role(config, role).items():
        score = score_profile(row, weights)["fit_score"].iloc[0]
        if pd.notna(score) and (best[1] is None or score > best[1]):
            best = (config["scouting_profiles"][role][key]["label"], float(score))
    return best


def strengths(player: pd.Series, config: dict, n: int = 3) -> list[str]:
    """The role features where this player's percentile is highest."""
    weights = _creditable(config["role_features"][player["role"]])
    pct = pd.Series({m: player.get(f"pct_{m}") for m in weights}).dropna()
    return pct.sort_values(ascending=False).head(n).index.tolist()


def squad_table(players: pd.DataFrame, config: dict, team_id: int) -> pd.DataFrame:
    """One row per qualified player at a club: role, minutes, rating, strengths.

    Sorted by role order from the config, then minutes, so the starters in each
    role come first.
    """
    squad = players[players["team_id"] == team_id].copy()
    if squad.empty:
        return squad
    squad["rating"] = role_rating(squad, config)
    fits = [best_profile(squad.loc[[i]], config) for i in squad.index]
    squad["profile"] = [f[0] for f in fits]
    squad["profile_fit"] = [f[1] for f in fits]
    squad["strengths"] = squad.apply(lambda p: strengths(p, config), axis=1)
    order = {g["key"]: i for i, g in enumerate(config["role_groups"])}
    squad["role_order"] = squad["role"].map(order)
    return (squad.sort_values(["role_order", "minutes"], ascending=[True, False])
            .drop(columns="role_order").reset_index(drop=True))



def _starter_score(group: pd.DataFrame, n: int) -> float:
    """Minutes-weighted mean rating of the top-n players by minutes."""
    starters = group.dropna(subset=["rating"]).nlargest(n, "minutes")
    if starters.empty:
        return float("nan")
    return float((starters["rating"] * starters["minutes"]).sum() / starters["minutes"].sum())


def role_strength(players: pd.DataFrame, config: dict, team_id: int) -> pd.DataFrame:
    """Per role: how the club's first-choice unit ranks against the league.

    Columns: role, starters (names' count), score (minutes-weighted rating),
    rank / of (club rank among clubs that have the role), verdict
    (Strong / Average / Weak), weakest (lowest-rated starter), depth (reserves
    who clear the minutes bar), best_reserve (rating of the best of them) and
    thin (fewer players above the minutes bar than the starters plus one).
    """
    settings = config["club_diagnosis"]
    rated = players.copy()
    rated["rating"] = role_rating(rated, config)

    rows = []
    for role, n in settings["starters_per_role"].items():
        in_role = rated[rated["role"] == role]
        scores = in_role.groupby("team_id").apply(
            lambda g, n=n: _starter_score(g, n), include_groups=False).dropna()
        if team_id not in scores.index:
            rows.append({"role": role, "starters": 0, "score": float("nan"),
                         "rank": None, "of": len(scores), "verdict": "No data",
                         "weakest": None, "depth": 0, "best_reserve": float("nan"),
                         "thin": True})
            continue
        rank = int(scores.rank(ascending=False, method="min")[team_id])
        total = len(scores)
        if rank <= max(1, round(total * settings["strong_rank_share"])):
            verdict = "Strong"
        elif rank > total - max(1, round(total * settings["weak_rank_share"])):
            verdict = "Weak"
        else:
            verdict = "Average"

        club = in_role[in_role["team_id"] == team_id].dropna(subset=["rating"])
        starters = club.nlargest(n, "minutes")
        reserves = club.drop(starters.index)
        cover = reserves[reserves["minutes"] >= settings["depth_min_minutes"]]
        depth = len(cover)
        best_reserve = float(cover["rating"].max()) if depth else float("nan")
        weakest = starters.nsmallest(1, "rating").iloc[0] if not starters.empty else None
        rows.append({
            "role": role, "starters": len(starters), "score": float(scores[team_id]),
            "rank": rank, "of": total, "verdict": verdict,
            "weakest": weakest, "depth": depth, "best_reserve": best_reserve,
            "thin": bool(len(starters) < n or depth == 0),
        })
    return pd.DataFrame(rows)


def team_metric_standing(team_season: pd.DataFrame, config: dict, team: str) -> pd.DataFrame:
    """A club's rank on each directional team metric, best first.

    `rank` is 1 for the best club in the league, taking the metric's direction
    from `club_diagnosis.team_metric_direction` into account, so rank 1 of 20 is
    always "best" whether the metric is better high (pass completion) or better
    low (PPDA, turnovers). `standing` is the same thing as a 0-100 score where
    100 is the best club.
    """
    directions = config["club_diagnosis"]["team_metric_direction"]
    rows = []
    for metric, direction in directions.items():
        values = team_season.set_index("team")[f"{metric}_mean"].dropna()
        if team not in values.index:
            continue
        ascending = direction == "low"
        rank = int(values.rank(ascending=ascending, method="min")[team])
        total = len(values)
        rows.append({
            "metric": metric, "value": float(values[team]),
            "league_median": float(values.median()), "direction": direction,
            "rank": rank, "of": total,
            "standing": (total - rank) / (total - 1) * 100 if total > 1 else 50.0,
        })
    return pd.DataFrame(rows).sort_values("rank", ascending=True).reset_index(drop=True)


def default_gap_role(strength: pd.DataFrame) -> str:
    """The role most worth looking at first: Weak, then no data, then thin, then Average."""
    order = {"Weak": 0, "No data": 1, "Average": 2, "Strong": 3}
    ranked = strength.assign(_verdict=strength["verdict"].map(order),
                             _depth=~strength["thin"]).sort_values(["_verdict", "_depth"])
    return str(ranked.iloc[0]["role"])
