"""Streamlit widgets shared by the pages that feed the shortlist."""

from __future__ import annotations

import streamlit as st

from ..scouting import store


def shortlist_button(player_id: int, key: str, list_name: str = store.DEFAULT_LIST) -> None:
    """Add a player to the shortlist, or show that they are already on it."""
    if store.is_shortlisted(player_id):
        st.button("On shortlist", icon=":material/bookmark_added:", key=key,
                  disabled=True)
    elif st.button("Shortlist", icon=":material/bookmark_add:", key=key):
        store.add_to_shortlist(player_id, list_name)
        st.rerun()
