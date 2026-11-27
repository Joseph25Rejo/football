"""Scout players: filter by role, minutes and percentile floors, rank by profile fit."""

import streamlit as st

from src.app import data, routing
from src.app.labels import pretty
from src.app.scouting_ui import shortlist_button
from src.features.player_season import METRIC_COLUMNS
from src.scouting.criteria import filter_players
from src.scouting.profiles import profiles_for_role, score_profile, top_drivers

st.title(":material/radar: Scout players")
st.caption(
    "Set what you need: a role, a minimum of minutes, and the percentile a player "
    "must reach on the metrics that matter. Optionally rank the results against a "
    "target profile. All percentiles are **within the player's role**."
)

config = data.config()
players = data.players()
role_names = {g["key"]: g["name"] for g in config["role_groups"]}
teams = players[["team_id", "team"]].drop_duplicates().sort_values("team")

with st.container(border=True):
    c1, c2, c3 = st.columns([2, 2, 3])
    role = c1.selectbox("Role", list(role_names), format_func=role_names.get)
    min_minutes = c2.slider("Minimum minutes", 600, 3400, 900, step=100)
    profiles = profiles_for_role(config, role)
    profile_key = c3.selectbox(
        "Target profile (optional)", [None, *profiles],
        format_func=lambda k: "No profile — sort by criteria" if k is None
        else config["scouting_profiles"][role][k]["label"],
    )

    c4, c5 = st.columns(2)
    own = c4.multiselect("Only these clubs", teams["team"], placeholder="Any club")
    skip = c5.multiselect("Exclude these clubs", teams["team"],
                          placeholder="e.g. your own club")

    role_metrics = list(config["role_features"][role])
    metrics = [m for m in METRIC_COLUMNS if m in role_metrics]
    chosen = st.multiselect(
        "Must be strong on", metrics, format_func=pretty,
        placeholder="Pick metrics to set a percentile floor on",
    )
    floor = st.slider("Minimum percentile on each chosen metric", 0, 99, 75) / 100

team_ids = teams.loc[teams["team"].isin(own), "team_id"].tolist()
skip_ids = teams.loc[teams["team"].isin(skip), "team_id"].tolist()

pool = players
results = filter_players(
    pool, role=role, min_minutes=min_minutes,
    thresholds={m: floor for m in chosen},
    team_ids=team_ids, exclude_team_ids=skip_ids,
)

weights = profiles.get(profile_key) if profile_key else None
if weights is not None and not results.empty:
    scored = score_profile(results, weights, config["similarity"]["min_feature_coverage"])
    results = results.join(scored)
    results["drivers"] = results.apply(
        lambda r: ", ".join(pretty(m) for m in top_drivers(r, weights)), axis=1)
    results = results.dropna(subset=["fit_score"]).sort_values("fit_score", ascending=False)

st.subheader(f"{len(results)} players match")
if results.empty:
    st.info("Nothing meets every criterion. Lower the percentile floor or the minutes.",
            icon=":material/info:")
    st.stop()

for m in chosen:
    results[f"p_{m}"] = results[f"pct_{m}"] * 100
shown = results.head(50)
columns = ["display_name", "team", "primary_position", "minutes"]
config_cols = {
    "display_name": st.column_config.TextColumn("Player"),
    "team": st.column_config.TextColumn("Club"),
    "primary_position": st.column_config.TextColumn("Position"),
    "minutes": st.column_config.NumberColumn("Minutes", format="%.0f"),
}
if weights is not None:
    columns += ["fit_score", "drivers"]
    config_cols["fit_score"] = st.column_config.ProgressColumn(
        "Profile fit", min_value=0, max_value=100, format="%.0f")
    config_cols["drivers"] = st.column_config.TextColumn("Strongest on")
for m in chosen:
    columns.append(f"p_{m}")
    config_cols[f"p_{m}"] = st.column_config.NumberColumn(
        f"{pretty(m)} (pct)", format="%.0f")

st.dataframe(shown[columns], hide_index=True, width="stretch", column_config=config_cols)
st.caption(
    "Showing the top 50. Percentiles rank a player against others in the same role "
    "in this season only. Profile fit is descriptive: it measures how closely the "
    "numbers match a style, not how good the player is."
)
st.download_button(
    "Download results (CSV)",
    results[columns].to_csv(index=False).encode("utf-8"),
    file_name="scouting_results.csv", mime="text/csv",
    icon=":material/download:",
)

st.divider()
st.subheader("Act on a result")
for _, p in shown.head(15).iterrows():
    cols = st.columns([3, 2, 1, 1])
    cols[0].markdown(f"**{p['display_name']}** · {p['team']}")
    if weights is not None:
        cols[1].markdown(f"fit **{p['fit_score']:.0f}**")
    if cols[2].button("Profile", key=f"scout_profile_{p['player_id']}"):
        routing.go(routing.PLAYER_PROFILE, **{routing.PLAYER: int(p["player_id"])})
    with cols[3]:
        shortlist_button(int(p["player_id"]), key=f"scout_short_{p['player_id']}")
