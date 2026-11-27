"""A one-page club scouting report, as Markdown.

Plain text on purpose: it opens anywhere, pastes into an email or a document,
and needs no rendering library. Pure function of the frames the page already
holds, so the page and the file can never disagree.
"""

from __future__ import annotations

import pandas as pd

from ..app.labels import format_value, pretty


def _name(row: pd.Series) -> str:
    nick = row.get("nickname")
    return nick if isinstance(nick, str) and nick.strip() else row["player_name"]


def club_report_markdown(
    team: str,
    season_label: str,
    role_names: dict[str, str],
    squad: pd.DataFrame,
    strength: pd.DataFrame,
    standing: pd.DataFrame,
    targets: pd.DataFrame | None = None,
    target_label: str = "",
    cluster_label: str | None = None,
) -> str:
    """Assemble the report: squad, strong and thin positions, weak stats, targets."""
    lines = [f"# {team}: scouting report ({season_label})", ""]
    if cluster_label:
        lines += [f"**Playing style:** {cluster_label}", ""]
    lines += [
        "_Descriptive only. Ratings are within-role percentiles for this league and "
        "season; they are not a verdict on quality, and low-possession sides rate low._",
        "",
        "## Positions", "",
        "| Role | Verdict | League rank | Unit rating | Depth | Lowest-rated starter |",
        "|---|---|---|---|---|---|",
    ]
    for _, r in strength.iterrows():
        if r["rank"] is None:
            lines.append(f"| {role_names[r['role']]} | No data | - | - | - | - |")
            continue
        flag = r["verdict"] + (" (thin)" if r["thin"] else "")
        lines.append(
            f"| {role_names[r['role']]} | {flag} | {r['rank']} of {r['of']} | "
            f"{r['score']:.0f} | {r['depth']} | "
            f"{_name(r['weakest'])} ({r['weakest']['rating']:.0f}) |")

    lines += ["", "## Squad", ""]
    for role, group in squad.groupby("role", sort=False):
        lines += [f"**{role_names[role]}**", ""]
        for _, p in group.iterrows():
            kind = f"{p['profile']} ({p['profile_fit']:.0f})" if pd.notna(p["profile"]) else "-"
            lines.append(f"- {_name(p)}: rating {p['rating']:.0f}, {p['minutes']:.0f} min, "
                         f"{kind}; strongest on "
                         f"{', '.join(pretty(m) for m in p['strengths'])}")
        lines.append("")

    def _metric_lines(frame: pd.DataFrame) -> list[str]:
        return [f"- {pretty(m['metric'])}: {format_value(m['metric'], m['value'])} "
                f"(league median {format_value(m['metric'], m['league_median'])}), "
                f"rank {m['rank']} of {m['of']}" for _, m in frame.iterrows()]

    lines += ["## Weakest statistics", ""]
    lines += _metric_lines(standing.sort_values("rank", ascending=False).head(5))
    lines += ["", "## Strongest statistics", "", *_metric_lines(standing.head(5))]

    if targets is not None and not targets.empty:
        lines += ["", f"## Targets: {target_label}", ""]
        for _, t in targets.head(10).iterrows():
            why = ", ".join(pretty(m) for m in t["why"])
            lines.append(f"- {_name(t)} ({t['team']}, {t['role']}): score {t['score']:.0f}; "
                         f"{why}")
    lines += ["", "_Source: StatsBomb Open Data. Candidates are limited to this dataset._", ""]
    return "\n".join(lines)
