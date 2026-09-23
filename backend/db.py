"""BuildWatch backend — SQLite schema and helpers."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "buildwatch.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS objects(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'Жильё'
);
CREATE TABLE IF NOT EXISTS snapshots(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  object_id INTEGER NOT NULL REFERENCES objects(id),
  filename TEXT NOT NULL,
  src TEXT NOT NULL,                -- samples|uploads
  captured_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',  -- new|detected|empty|processing
  width INTEGER NOT NULL,
  height INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS detections(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
  model TEXT NOT NULL,
  label TEXT NOT NULL,
  score REAL NOT NULL,
  x1 REAL NOT NULL, y1 REAL NOT NULL, x2 REAL NOT NULL, y2 REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS stages(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  object_id INTEGER NOT NULL REFERENCES objects(id),
  position INTEGER NOT NULL,
  kind TEXT NOT NULL,               -- ground|excavation|frame|facade|roof|other
  name TEXT NOT NULL,
  date_from TEXT NOT NULL,
  date_to TEXT NOT NULL,
  status TEXT NOT NULL              -- done|current|future
);
CREATE TABLE IF NOT EXISTS warnings(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  object_id INTEGER NOT NULL REFERENCES objects(id),
  snapshot_id INTEGER NOT NULL REFERENCES snapshots(id),
  rule TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  why TEXT NOT NULL,
  source TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open',  -- open|confirmed|dismissed
  severity TEXT NOT NULL DEFAULT 'violation'  -- violation|review
);
CREATE TABLE IF NOT EXISTS catalog(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  applies TEXT NOT NULL             -- csv of building types from ЛТЦ
);
"""


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init() -> None:
    con = connect()
    con.executescript(SCHEMA)
    con.commit()
    con.close()


def query(sql: str, args: tuple = ()) -> list[sqlite3.Row]:
    with connect() as con:
        return con.execute(sql, args).fetchall()


def execute(sql: str, args: tuple = ()) -> int:
    con = connect()
    try:
        cur = con.execute(sql, args)
        con.commit()
        return cur.lastrowid or cur.rowcount
    finally:
        con.close()
