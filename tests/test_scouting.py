"""Unit tests for the scouting logic: criteria filter, profile fit, shortlist store."""

import numpy as np
import pandas as pd
import pytest

from src.scouting import store
from src.scouting.criteria import filter_players
from src.scouting.profiles import score_profile, top_drivers


@pytest.fixture
def season():
    return pd.DataFrame({
        "player_id": [1, 2, 3, 4],
        "role": ["CB", "CB", "CB", "ST"],
        "team_id": [10, 10, 20, 30],
        "minutes": [2000, 800, 1500, 1800],
        "pct_a": [0.9, 0.95, 0.5, 0.99],
        "pct_b": [0.8, 0.2, np.nan, 0.9],
    })


def test_filter_applies_role_minutes_and_floor(season):
    out = filter_players(season, role="CB", min_minutes=1000, thresholds={"a": 0.8})
    assert out["player_id"].tolist() == [1]


def test_filter_excludes_missing_values_on_a_thresholded_metric(season):
    out = filter_players(season, role="CB", thresholds={"b": 0.1})
    assert 3 not in out["player_id"].tolist()


def test_filter_team_include_and_exclude(season):
    assert filter_players(season, role="CB", team_ids=[20])["player_id"].tolist() == [3]
    assert 3 not in filter_players(season, role="CB", exclude_team_ids=[20])["player_id"].tolist()


def test_filter_ranks_by_mean_threshold_percentile(season):
    out = filter_players(season, role="CB", thresholds={"a": 0.1, "b": 0.1})
    assert out["player_id"].tolist() == [1, 2]


def test_filter_rejects_unknown_metric(season):
    with pytest.raises(KeyError):
        filter_players(season, thresholds={"nope": 0.5})


def test_profile_score_is_weighted_mean_percentile(season):
    out = score_profile(season, {"a": 3.0, "b": 1.0})
    assert out.loc[0, "fit_score"] == pytest.approx((0.9 * 3 + 0.8) / 4 * 100)
    assert out.loc[0, "contrib_a"] > out.loc[0, "contrib_b"]
    assert top_drivers(out.loc[0], {"a": 3.0, "b": 1.0}, n=1) == ["a"]


def test_profile_score_needs_minimum_coverage(season):
    # player 3 lacks b, which carries half the weight: below 0.7 coverage.
    assert np.isnan(score_profile(season, {"a": 1.0, "b": 1.0}).loc[2, "fit_score"])
    # with b minor, coverage is high enough and the score uses a alone.
    assert score_profile(season, {"a": 4.0, "b": 1.0}).loc[2, "fit_score"] == pytest.approx(50)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "scouting.duckdb"


def test_shortlist_add_is_idempotent_and_persists(db):
    store.add_to_shortlist(7, path=db)
    store.add_to_shortlist(7, path=db)
    assert len(store.shortlist(path=db)) == 1
    assert store.is_shortlisted(7, path=db)


def test_status_update_and_remove(db):
    store.add_to_shortlist(7, path=db)
    store.set_status(7, "Priority", path=db)
    assert store.shortlist(path=db)["status"].tolist() == ["Priority"]
    store.remove_from_shortlist(7, path=db)
    assert store.shortlist(path=db).empty


def test_invalid_status_is_rejected(db):
    with pytest.raises(ValueError):
        store.add_to_shortlist(7, status="Bought", path=db)


def test_notes_are_stored_newest_first_and_validated(db):
    store.add_note(7, "first", 3, path=db)
    store.add_note(7, "second", None, path=db)
    assert store.notes_for(7, path=db)["note"].tolist() == ["second", "first"]
    with pytest.raises(ValueError):
        store.add_note(7, "   ", path=db)
    with pytest.raises(ValueError):
        store.add_note(7, "x", 9, path=db)


# --- club diagnosis ---------------------------------------------------------

from src.scouting.diagnosis import role_rating, role_strength, strengths


@pytest.fixture
def cfg():
    return {
        "similarity": {"min_feature_coverage": 0.7},
        "role_features": {"CB": {"a": 1.0, "turnovers_p90": 5.0}},
        "club_diagnosis": {
            "starters_per_role": {"CB": 2}, "depth_min_minutes": 900,
            "strong_rank_share": 0.34, "weak_rank_share": 0.34,
        },
    }


def _cbs(rows):
    return pd.DataFrame(
        [{"player_id": i, "team_id": t, "role": "CB", "minutes": m,
          "pct_a": a, "pct_turnovers_p90": 1.0, "player_name": f"p{i}", "nickname": None}
         for i, (t, m, a) in enumerate(rows)])


def test_rating_ignores_turnover_metrics(cfg):
    players = _cbs([(1, 2000, 0.5)])
    # turnovers percentile is 1.0 with weight 5; if counted the rating would be ~92.
    assert role_rating(players, cfg).iloc[0] == pytest.approx(50)
    assert strengths(players.iloc[0], cfg) == ["a"]


def test_role_strength_ranks_clubs_and_flags_thin(cfg):
    rows = []
    for team, quality in zip(range(1, 7), [0.9, 0.8, 0.6, 0.5, 0.3, 0.1], strict=True):
        rows += [(team, 2000, quality), (team, 1900, quality)]
    rows += [(1, 1000, 0.9)]                       # club 1 has a reserve with minutes
    players = _cbs(rows)
    best = role_strength(players, cfg, 1).iloc[0]
    worst = role_strength(players, cfg, 6).iloc[0]
    assert (best["rank"], best["verdict"], best["thin"], best["depth"]) == (1, "Strong", False, 1)
    assert (worst["rank"], worst["verdict"], worst["thin"]) == (6, "Weak", True)


def test_role_strength_handles_a_club_with_no_players_in_the_role(cfg):
    players = _cbs([(1, 2000, 0.5), (1, 1900, 0.5)])
    out = role_strength(players, cfg, 99).iloc[0]
    assert out["verdict"] == "No data" and out["thin"]


def test_team_metric_standing_respects_direction():
    from src.scouting.diagnosis import team_metric_standing

    teams = pd.DataFrame({
        "team": ["A", "B", "C"],
        "pass_completion_mean": [0.9, 0.8, 0.7],   # better high
        "ppda_mean": [9.0, 11.0, 13.0],            # better low
    })
    cfg = {"club_diagnosis": {"team_metric_direction": {
        "pass_completion": "high", "ppda": "low"}}}
    out = team_metric_standing(teams, cfg, "A").set_index("metric")
    assert out.loc["pass_completion", "rank"] == 1
    assert out.loc["ppda", "rank"] == 1            # lowest PPDA is the best
    assert out.loc["ppda", "standing"] == 100
    worst = team_metric_standing(teams, cfg, "C").set_index("metric")
    assert worst.loc["ppda", "rank"] == 3 and worst.loc["ppda", "standing"] == 0
