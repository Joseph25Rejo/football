"""Tests for target lists: own club excluded, role/minutes filters, mappings valid."""

import pandas as pd
import pytest

from src.config import load_config
from src.features.player_season import METRIC_COLUMNS
from src.scouting.targets import role_targets, weakness_targets


def _pool():
    rows = []
    for pid, team, role, minutes, a in [
        (1, 1, "ST", 2000, 0.40), (2, 1, "ST", 1500, 0.30),   # the club's own strikers
        (3, 2, "ST", 1800, 0.90), (4, 3, "ST", 500, 0.99),    # outside; 4 lacks minutes
        (5, 2, "CB", 2000, 0.95),                              # wrong role
    ]:
        rows.append({"player_id": pid, "team_id": team, "role": role, "minutes": minutes,
                     "pct_a": a, "pct_b": a, "pct_turnovers_p90": 1.0,
                     "player_name": f"p{pid}", "nickname": None})
    return pd.DataFrame(rows)


@pytest.fixture
def cfg():
    return {
        "similarity": {"min_feature_coverage": 0.7},
        "role_features": {"ST": {"a": 1.0}, "CB": {"a": 1.0}},
        "scouting_profiles": {"ST": {"p": {"label": "P", "metrics": {"a": 1.0}}}},
        "club_diagnosis": {"starters_per_role": {"ST": 1, "CB": 2}},
        "team_weakness_targets": {"shots": {"roles": ["ST"], "player_metrics": ["a", "b"]}},
    }


def test_role_targets_exclude_own_club_other_roles_and_low_minutes(cfg):
    found, weakest = role_targets(_pool(), cfg, team_id=1, role="ST", min_minutes=900)
    assert found["player_id"].tolist() == [3]
    assert weakest == pytest.approx(40)                 # one starter: top ST by minutes
    assert found.loc[0, "vs_weakest"] == pytest.approx(50)


def test_role_targets_can_rank_by_a_profile(cfg):
    found, _ = role_targets(_pool(), cfg, 1, "ST", profile_key="p", min_minutes=900)
    assert found.loc[0, "score"] == pytest.approx(90)


def test_weakness_targets_use_the_mapped_roles_and_metrics(cfg):
    found = weakness_targets(_pool(), cfg, 1, "shots", min_minutes=900)
    assert found["player_id"].tolist() == [3]
    with pytest.raises(KeyError):
        weakness_targets(_pool(), cfg, 1, "unmapped")


def test_every_weakness_mapping_points_at_real_columns():
    cfg = load_config()
    direction = cfg["club_diagnosis"]["team_metric_direction"]
    for metric, spec in cfg["team_weakness_targets"].items():
        assert metric in direction, f"{metric} is mapped but never judged"
        assert set(spec["roles"]) <= set(cfg["role_features"])
        assert set(spec["player_metrics"]) <= set(METRIC_COLUMNS)
