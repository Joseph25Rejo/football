"""Shortlist and scouting notes: the scout's own working list."""

import streamlit as st

from src.app import data, routing
from src.scouting import store

st.title(":material/bookmark: Shortlist & notes")
st.caption(
    "Your working list. It is saved on this machine, separate from the match data, "
    "so rebuilding the data never loses it."
)

players = data.players().set_index("player_id")
lists = store.list_names()

top = st.columns([3, 3])
list_name = top[0].selectbox("List", lists)
new_name = top[1].text_input("Or start a new list", placeholder="e.g. Left-back targets")
if new_name.strip():
    list_name = new_name.strip()

entries = store.shortlist(list_name)
if entries.empty:
    st.info("This list is empty. Use **Shortlist** on a result in Scout players, "
            "or add someone below.", icon=":material/bookmark_add:")

with st.expander("Add a player", expanded=entries.empty):
    options = data.player_options()
    pick = st.selectbox("Player", options["label"], index=None,
                        placeholder="Search for a player…", key="add_pick")
    if pick and st.button("Add to list", icon=":material/add:", key="add_btn"):
        store.add_to_shortlist(int(options.loc[options["label"] == pick,
                                               "player_id"].iloc[0]), list_name)
        st.rerun()

if not entries.empty:
    table = entries.copy()
    table["player"] = table["player_id"].map(lambda i: data.display_name(players.loc[i]))
    table["club"] = table["player_id"].map(players["team"])
    table["role"] = table["player_id"].map(players["role"])
    table["minutes"] = table["player_id"].map(players["minutes"])
    st.dataframe(
        table[["player", "club", "role", "minutes", "status", "added_at"]],
        hide_index=True, width="stretch",
        column_config={
            "minutes": st.column_config.NumberColumn("Minutes", format="%.0f"),
            "added_at": st.column_config.DatetimeColumn("Added", format="D MMM YYYY"),
        },
    )
    st.download_button(
        "Download shortlist (CSV)",
        table[["player", "club", "role", "minutes", "status"]].to_csv(index=False)
        .encode("utf-8"),
        file_name=f"{list_name}.csv", mime="text/csv", icon=":material/download:",
    )

    st.divider()
    st.subheader("Manage a player")
    chosen = st.selectbox("Player", table["player"], key="manage_pick")
    pid = int(table.loc[table["player"] == chosen, "player_id"].iloc[0])
    current = table.loc[table["player_id"] == pid, "status"].iloc[0]

    a, b, c = st.columns([2, 1, 1])
    status = a.selectbox("Status", store.STATUSES, index=store.STATUSES.index(current))
    if status != current:
        store.set_status(pid, status, list_name)
        st.rerun()
    if b.button("Open profile", icon=":material/person:"):
        routing.go(routing.PLAYER_PROFILE, **{routing.PLAYER: pid})
    if c.button("Remove", icon=":material/delete:"):
        store.remove_from_shortlist(pid, list_name)
        st.rerun()

    st.markdown("**Scouting notes**")
    with st.form("note_form", clear_on_submit=True):
        note = st.text_area("Note", placeholder="What did you see?")
        rating = st.select_slider("Rating (optional)", [None, 1, 2, 3, 4, 5],
                                  format_func=lambda r: "—" if r is None else str(r))
        if st.form_submit_button("Save note", icon=":material/note_add:") and note.strip():
            store.add_note(pid, note, rating)
            st.rerun()
    for _, n in store.notes_for(pid).iterrows():
        stars = "" if n["rating"] is None or n["rating"] != n["rating"] else \
            f" · {int(n['rating'])}/5"
        st.markdown(f"> {n['note']}\n\n<small>{n['created_at']:%d %b %Y}{stars}</small>",
                    unsafe_allow_html=True)
