"""Club scouting: a squad's make-up, where it is strong or thin, and who could help."""

import pandas as pd
import streamlit as st

from src.app import data, routing
from src.app.labels import format_value, pretty
from src.app.scouting_ui import shortlist_button
from src.scouting.diagnosis import (
    default_gap_role,
    role_strength,
    squad_table,
    team_metric_standing,
)
from src.scouting.profiles import profiles_for_role
from src.scouting.report import club_report_markdown
from src.scouting.targets import role_targets, weakness_targets

st.title(":material/groups: Club scouting")
st.caption(
    "Pick a club to see its squad, where it is strong or thin, which statistics it is "
    "weak at, and who could help. Everything is **descriptive**: ratings are "
    "percentiles within a player's role, not a verdict on quality."
)

config = data.config()
players = data.players()
season = data.team_season()
role_names = {g["key"]: g["name"] for g in config["role_groups"]}

team_names = sorted(season["team"])
requested = routing.param(routing.TEAM)
default_index = team_names.index(requested) if requested in team_names else None

with st.container(border=True):
    team = st.selectbox("Club", team_names, index=default_index,
                        placeholder="Select a club…")

if team is None:
    st.info("Select a club to begin.", icon=":material/groups:")
    st.stop()

if routing.param(routing.TEAM) != team:
    st.query_params[routing.TEAM] = team

team_id = int(season.loc[season["team"] == team, "team_id"].iloc[0])
squad = squad_table(players, config, team_id)
strength = role_strength(players, config, team_id)
standing = team_metric_standing(season, config, team)

style_rows = data.team_style()
style_rows = style_rows[style_rows["team"] == team]
gap_role = default_gap_role(strength)
report_targets, _ = role_targets(players, config, team_id, gap_role)
report = club_report_markdown(
    team, config["dataset"]["season_name"], role_names, squad, strength, standing,
    report_targets, f"{role_names[gap_role]} (biggest gap)",
    style_rows.iloc[0]["cluster_label"] if not style_rows.empty else None,
)
st.download_button("Download club report (Markdown)", report.encode("utf-8"),
                   file_name=f"{team}_scouting_report.md", mime="text/markdown",
                   icon=":material/description:")

tab_squad, tab_gaps, tab_weak, tab_targets = st.tabs(
    ["Squad", "Strengths & gaps", "Weak stats", "Targets"])

with tab_squad:
    if squad.empty:
        st.info("No qualified players for this club.", icon=":material/info:")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Qualified players", len(squad), border=True)
        m2.metric("Average rating", f"{squad['rating'].mean():.0f}", border=True)
        top = squad.sort_values("rating", ascending=False).iloc[0]
        m3.metric("Top rating", f"{top['rating']:.0f}", border=True)
        st.caption(f"Highest rated: **{data.display_name(top)}** "
                   f"({top['primary_position']}, {top['role']})")

        for role, group in squad.groupby("role", sort=False):
            st.subheader(role_names[role])
            view = group.copy()
            view["Player"] = view.apply(data.display_name, axis=1)
            view["Strongest on"] = view["strengths"].apply(
                lambda ms: ", ".join(pretty(m) for m in ms))
            view["Type"] = view.apply(
                lambda r: "—" if pd.isna(r["profile"])
                else f"{r['profile']} ({r['profile_fit']:.0f})", axis=1)
            st.dataframe(
                view[["Player", "primary_position", "minutes", "rating", "Type",
                      "Strongest on"]],
                hide_index=True, width="stretch",
                column_config={
                    "primary_position": st.column_config.TextColumn("Position"),
                    "minutes": st.column_config.NumberColumn("Minutes", format="%.0f"),
                    "rating": st.column_config.ProgressColumn(
                        "Rating", min_value=0, max_value=100, format="%.0f",
                        help="Weighted mean percentile on this role's features"),
                    "Type": st.column_config.TextColumn(
                        "Best-fit type (fit)",
                        help="The target profile this player's numbers match best"),
                },
            )
        st.caption(
            "Only players with enough minutes to be rated appear. **Rating** is the "
            "weighted mean of a player's within-role percentiles; turnover-style "
            "metrics are left out because a high value there is not a strength."
        )

        st.markdown("**Open a player**")
        pick = st.selectbox("Player", squad.apply(data.display_name, axis=1),
                            index=None, placeholder="Choose a player…")
        if pick:
            chosen = squad[squad.apply(data.display_name, axis=1) == pick].iloc[0]
            a, b = st.columns([1, 1])
            if a.button("Open profile", icon=":material/person:", key="club_profile"):
                routing.go(routing.PLAYER_PROFILE,
                           **{routing.PLAYER: int(chosen["player_id"])})
            with b:
                shortlist_button(int(chosen["player_id"]), key="club_shortlist")

with tab_gaps:
    st.caption(
        "Each role's first-choice unit (top players by minutes) is scored by its "
        "minutes-weighted rating and ranked against the other clubs. **Thin** means "
        "no reserve beyond the starters has played enough minutes."
    )
    colours = {"Strong": "green", "Average": "gray", "Weak": "red", "No data": "gray"}
    for _, r in strength.iterrows():
        with st.container(border=True):
            head, body = st.columns([2, 5])
            with head:
                st.markdown(f"**{role_names[r['role']]}**")
                st.badge(r["verdict"], color=colours[r["verdict"]])
                if r["thin"]:
                    st.badge("Thin", color="orange", icon=":material/warning:")
            with body:
                if r["rank"] is None:
                    st.write("No rated players in this role.")
                    continue
                a, b, c = st.columns(3)
                a.metric("League rank", f"{r['rank']} of {r['of']}")
                b.metric("Unit rating", f"{r['score']:.0f}")
                c.metric("Depth", r["depth"],
                         help="Reserves beyond the starters with enough minutes")
                weakest = r["weakest"]
                reserve = (f" · best reserve rated {r['best_reserve']:.0f}"
                           if r["depth"] else "")
                st.caption(
                    f"Lowest-rated starter: **{data.display_name(weakest)}** "
                    f"({weakest['rating']:.0f}) · starters counted: {r['starters']}"
                    f"{reserve}")
    st.caption(
        "Ratings reward how much a player does in the role's measured areas (passing, "
        "progression, defending actions), so a low-possession side can rank low in a role "
        "while winning matches. Read **Weak** as *thin on these statistics*, not as *bad*. "
        "Leicester's title-winning back line, for example, ranks near the bottom."
    )
with tab_weak:
    style = data.team_style()
    style_row = style[style["team"] == team]
    if not style_row.empty:
        st.markdown(f"**Playing style:** {style_row.iloc[0]['cluster_label']}")
    st.caption(
        "Only metrics with a clear direction of *better* are judged (e.g. fewer "
        "turnovers, more shots). Choices of style, such as width or long-ball share, "
        "are not treated as weaknesses. Rank 1 is the best club in the league."
    )

    def _table(frame: pd.DataFrame) -> pd.DataFrame:
        def fmt(column: str) -> list[str]:
            return [format_value(m, v)
                    for m, v in zip(frame["metric"], frame[column], strict=True)]

        out = pd.DataFrame({
            "Metric": frame["metric"].map(pretty),
            "This club": fmt("value"),
            "League median": fmt("league_median"),
            "Rank": [f"{r} of {o}" for r, o in zip(frame["rank"], frame["of"], strict=True)],
            "Standing": frame["standing"],
        })
        return out

    columns = {"Standing": st.column_config.ProgressColumn(
        "Standing", min_value=0, max_value=100, format="%.0f",
        help="100 = best club in the league on this metric")}
    st.subheader("Weakest areas")
    st.dataframe(_table(standing.sort_values("rank", ascending=False).head(5)),
                 hide_index=True, width="stretch", column_config=columns)
    st.subheader("Strongest areas")
    st.dataframe(_table(standing.head(5)), hide_index=True, width="stretch",
                 column_config=columns)
    with st.expander("All judged metrics"):
        st.dataframe(_table(standing), hide_index=True, width="stretch",
                     column_config=columns)

with tab_targets:
    st.caption(
        "Players from **other clubs** whose numbers point at a gap. Candidates are "
        "limited to this dataset (Premier League 2015/16). A good fit on paper says "
        "nothing about price, availability or whether a player suits the system."
    )
    mode = st.radio("Look for", ["Fill a position", "Fix a weak statistic"],
                    horizontal=True)
    min_minutes = st.slider("Minimum minutes", 600, 3000, 900, step=100,
                            key="target_minutes")

    def _target_table(frame: pd.DataFrame, extra: dict) -> None:
        view = frame.copy()
        view["Player"] = view.apply(data.display_name, axis=1)
        view["Why"] = view["why"].apply(lambda ms: ", ".join(pretty(m) for m in ms))
        columns = ["Player", "team", "role", "minutes", "score", *extra, "Why"]
        st.dataframe(
            view[columns], hide_index=True, width="stretch",
            column_config={
                "team": st.column_config.TextColumn("Club"),
                "role": st.column_config.TextColumn("Role"),
                "minutes": st.column_config.NumberColumn("Minutes", format="%.0f"),
                "score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=100, format="%.0f"),
                **extra,
            },
        )
        st.download_button(
            "Download targets (CSV)",
            view[columns].to_csv(index=False).encode("utf-8"),
            file_name=f"{team}_targets.csv", mime="text/csv",
            icon=":material/download:")
        st.markdown("**Act on a target**")
        for _, p in frame.head(10).iterrows():
            c = st.columns([3, 2, 1, 1.4])
            c[0].markdown(f"**{data.display_name(p)}** · {p['team']}")
            c[1].markdown(f"score **{p['score']:.0f}** · {p['role']}")
            if c[2].button("Profile", key=f"tg_profile_{p['player_id']}"):
                routing.go(routing.PLAYER_PROFILE, **{routing.PLAYER: int(p["player_id"])})
            with c[3]:
                shortlist_button(int(p["player_id"]), key=f"tg_short_{p['player_id']}")

    if mode == "Fill a position":
        roles = list(role_names)
        default = roles.index(default_gap_role(strength))
        a, b = st.columns(2)
        role = a.selectbox("Position", roles, index=default, format_func=role_names.get)
        profiles = profiles_for_role(config, role)
        profile_key = b.selectbox(
            "Rank by", [None, *profiles],
            format_func=lambda k: "Overall role rating" if k is None
            else config["scouting_profiles"][role][k]["label"])
        row = strength[strength["role"] == role].iloc[0]
        if row["rank"] is None:
            st.markdown(f"**{team}** has no rated {role_names[role]}.")
        else:
            flag = row["verdict"] + (", thin" if row["thin"] else "")
            st.markdown(f"**{team}** at {role_names[role]}: {flag} "
                        f"(rank {row['rank']} of {row['of']}).")
        found, weakest = role_targets(players, config, team_id, role, profile_key,
                                      min_minutes)
        if found.empty:
            st.info("No outside candidate clears those filters.", icon=":material/info:")
        else:
            if weakest == weakest:
                st.caption(f"Their weakest starter here is rated **{weakest:.0f}**; "
                           "**Rating vs weakest starter** shows who rates above that.")
            _target_table(found, {"vs_weakest": st.column_config.NumberColumn(
                "Rating vs weakest starter", format="%+.0f")})
    else:
        mapped = standing[standing["metric"].isin(config["team_weakness_targets"])]
        weakest_first = mapped.sort_values("rank", ascending=False)["metric"].tolist()
        metric = st.selectbox("Weak statistic", weakest_first, format_func=pretty,
                              help="Ordered with the club's weakest first")
        mapping = config["team_weakness_targets"][metric]
        row = standing[standing["metric"] == metric].iloc[0]
        st.markdown(
            f"**{pretty(metric)}**: {team} rank {row['rank']} of {row['of']}. "
            f"Looking at **{', '.join(role_names[r] for r in mapping['roles'])}** on "
            f"**{', '.join(pretty(m) for m in mapping['player_metrics'])}**.")
        st.caption("Which roles and player metrics address a team statistic is an "
                   "analytical judgement, not a proven link.")
        found = weakness_targets(players, config, team_id, metric, min_minutes)
        if found.empty:
            st.info("No outside candidate clears those filters.", icon=":material/info:")
        else:
            _target_table(found, {})
