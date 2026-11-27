"""The club report, the default gap role and the percentage labels."""

import pandas as pd

from src.app.labels import format_value
from src.scouting.diagnosis import default_gap_role
from src.scouting.report import club_report_markdown


def _strength(rows):
    return pd.DataFrame([{"role": r, "verdict": v, "thin": t, "rank": 5, "of": 20,
                          "score": 50.0, "depth": 1, "best_reserve": 40.0,
                          "weakest": pd.Series({"player_name": "Wk", "nickname": None,
                                                "rating": 41.0})}
                         for r, v, t in rows])


def test_default_gap_role_prefers_weak_then_thin():
    s = _strength([("CB", "Strong", True), ("FB", "Weak", False), ("CM", "Weak", True)])
    assert default_gap_role(s) == "CM"                 # both Weak: the thin one first
    s = _strength([("CB", "Strong", True), ("FB", "Average", False), ("CM", "Average", True)])
    assert default_gap_role(s) == "CM"


def test_completion_metrics_read_as_percentages():
    assert format_value("pressured_pass_completion", 0.72) == "72%"
    assert format_value("pass_completion", 0.8) == "80%"


def test_report_contains_every_section_and_the_caveat():
    squad = pd.DataFrame([{"role": "CB", "player_name": "Pat", "nickname": None,
                           "rating": 70.0, "minutes": 2000.0, "profile": "Stopper",
                           "profile_fit": 80.0, "strengths": ["padj_tackles_p90"]}])
    standing = pd.DataFrame([{"metric": "ppda", "value": 2.2, "league_median": 2.5,
                              "direction": "low", "rank": 3, "of": 20, "standing": 89.0}])
    targets = pd.DataFrame([{"player_name": "Quinn", "nickname": None, "team": "Rival",
                             "role": "CB", "score": 75.0, "why": ["padj_tackles_p90"]}])
    text = club_report_markdown("Club", "2015/2016", {"CB": "Centre-backs"}, squad,
                                _strength([("CB", "Strong", True)]), standing,
                                targets, "Centre-backs", "High press")
    for needle in ("# Club: scouting report", "High press", "## Positions",
                   "Strong (thin)", "Pat: rating 70", "## Weakest statistics",
                   "## Strongest statistics", "## Targets: Centre-backs", "Quinn (Rival",
                   "not a verdict on quality"):
        assert needle in text
