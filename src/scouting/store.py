"""Shortlists and scouting notes, kept in a small local DuckDB file.

Separate from the read-only analytical database on purpose: the marts are
derived data that can be rebuilt at any time, whereas shortlists and notes are
the scout's own work and must survive a rebuild. Each call opens and closes its
own connection, so Streamlit reruns never hold a write lock.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pandas as pd

from ..config import DATA_DIR

STORE_PATH_ENV_VAR = "FIP_SCOUTING_DB"
DEFAULT_PATH = DATA_DIR / "scouting.duckdb"
STATUSES = ["Watch", "Priority", "Contacted", "Rejected"]
DEFAULT_LIST = "Main shortlist"


def store_path() -> Path:
    return Path(os.environ.get(STORE_PATH_ENV_VAR) or DEFAULT_PATH)


@contextmanager
def _connect(path: Path | None = None):
    path = path or store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS shortlist (
                list_name VARCHAR, player_id BIGINT, status VARCHAR,
                added_at TIMESTAMP DEFAULT current_timestamp,
                PRIMARY KEY (list_name, player_id))"""
        )
        con.execute("CREATE SEQUENCE IF NOT EXISTS note_id_seq")
        con.execute(
            """CREATE TABLE IF NOT EXISTS notes (
                note_id BIGINT DEFAULT nextval('note_id_seq'), player_id BIGINT,
                note VARCHAR, rating INTEGER,
                created_at TIMESTAMP DEFAULT current_timestamp)"""
        )
        yield con
    finally:
        con.close()


def _check_status(status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")


def add_to_shortlist(player_id: int, list_name: str = DEFAULT_LIST,
                     status: str = "Watch", path: Path | None = None) -> None:
    _check_status(status)
    with _connect(path) as con:
        con.execute(
            "INSERT INTO shortlist (list_name, player_id, status) VALUES (?, ?, ?) "
            "ON CONFLICT DO NOTHING", [list_name, int(player_id), status])


def remove_from_shortlist(player_id: int, list_name: str = DEFAULT_LIST,
                          path: Path | None = None) -> None:
    with _connect(path) as con:
        con.execute("DELETE FROM shortlist WHERE list_name = ? AND player_id = ?",
                    [list_name, int(player_id)])


def set_status(player_id: int, status: str, list_name: str = DEFAULT_LIST,
               path: Path | None = None) -> None:
    _check_status(status)
    with _connect(path) as con:
        con.execute("UPDATE shortlist SET status = ? WHERE list_name = ? AND player_id = ?",
                    [status, list_name, int(player_id)])


def shortlist(list_name: str | None = None, path: Path | None = None) -> pd.DataFrame:
    with _connect(path) as con:
        if list_name:
            return con.execute(
                "SELECT * FROM shortlist WHERE list_name = ? ORDER BY added_at",
                [list_name]).df()
        return con.execute("SELECT * FROM shortlist ORDER BY list_name, added_at").df()


def list_names(path: Path | None = None) -> list[str]:
    with _connect(path) as con:
        names = [r[0] for r in con.execute(
            "SELECT DISTINCT list_name FROM shortlist ORDER BY 1").fetchall()]
    return names or [DEFAULT_LIST]


def is_shortlisted(player_id: int, path: Path | None = None) -> bool:
    with _connect(path) as con:
        return con.execute("SELECT count(*) FROM shortlist WHERE player_id = ?",
                           [int(player_id)]).fetchone()[0] > 0


def add_note(player_id: int, note: str, rating: int | None = None,
             path: Path | None = None) -> None:
    if not note.strip():
        raise ValueError("note is empty")
    if rating is not None and not 1 <= rating <= 5:
        raise ValueError("rating must be 1-5")
    with _connect(path) as con:
        con.execute("INSERT INTO notes (player_id, note, rating) VALUES (?, ?, ?)",
                    [int(player_id), note.strip(), rating])


def notes_for(player_id: int, path: Path | None = None) -> pd.DataFrame:
    with _connect(path) as con:
        return con.execute(
            "SELECT note_id, note, rating, created_at FROM notes "
            "WHERE player_id = ? ORDER BY created_at DESC, note_id DESC",
            [int(player_id)]).df()
