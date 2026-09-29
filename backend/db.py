"""BuildWatch backend — SQLite schema and helpers."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("BUILDWATCH_SQLITE_PATH", str(Path(__file__).resolve().parent / "buildwatch.db")))
DATABASE_URL = os.getenv("BUILDWATCH_DATABASE_URL", "")

def _pg():
    if not DATABASE_URL.startswith("postgresql"):
        return None
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def _sql(sql: str) -> str:
    return sql.replace("?", "%s") if DATABASE_URL.startswith("postgresql") else sql

SCHEMA = """
CREATE TABLE IF NOT EXISTS objects(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  type TEXT NOT NULL DEFAULT 'Жильё',
  district TEXT NOT NULL DEFAULT '',
  address TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS snapshots(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  object_id INTEGER NOT NULL REFERENCES objects(id),
  filename TEXT NOT NULL,
  src TEXT NOT NULL,                -- samples|uploads
  captured_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'new',  -- new|detected|empty|processing|failed
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
CREATE TABLE IF NOT EXISTS object_comments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  object_id INTEGER NOT NULL REFERENCES objects(id),
  body TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS object_events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  object_id INTEGER NOT NULL REFERENCES objects(id),
  stage_id INTEGER REFERENCES stages(id),
  snapshot_id INTEGER REFERENCES snapshots(id),
  event_type TEXT NOT NULL DEFAULT 'human',
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  event_date TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'viewer',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER REFERENCES users(id),
  action TEXT NOT NULL,
  entity TEXT,
  entity_id INTEGER,
  details TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS detection_jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  snapshot_id INTEGER NOT NULL UNIQUE REFERENCES snapshots(id),
  model TEXT NOT NULL DEFAULT 'yolo_world',
  status TEXT NOT NULL DEFAULT 'queued',
  attempts INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TEXT,
  finished_at TEXT
);
CREATE TABLE IF NOT EXISTS catalog(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT NOT NULL,
  name TEXT NOT NULL,
  applies TEXT NOT NULL             -- csv of building types from ЛТЦ
);
CREATE TABLE IF NOT EXISTS assistant_proposals(
  id TEXT PRIMARY KEY,
  object_id INTEGER NOT NULL REFERENCES objects(id),
  stage_id INTEGER NOT NULL REFERENCES stages(id),
  old_from TEXT NOT NULL,
  old_to TEXT NOT NULL,
  new_from TEXT NOT NULL,
  new_to TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


# Project metadata added after the first schema; migrated in place by init().
OBJECT_TEXT_COLUMNS = ("district", "address", "description")


def connect():
    pg = _pg()
    if pg is not None:
        return pg
    con = sqlite3.connect(DB_PATH, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=10000")
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init() -> None:
    if DATABASE_URL.startswith("postgresql"):
        migration = Path(__file__).resolve().parent.parent / "migrations" / "001_production.sql"
        with connect() as con:
            for statement in migration.read_text(encoding="utf-8").split(";"):
                if statement.strip(): con.execute(statement)
            con.commit()
        return
    con = connect()
    con.executescript(SCHEMA)
    columns = {row["name"] for row in con.execute("PRAGMA table_info(detection_jobs)")}
    if "model" not in columns:
        con.execute("ALTER TABLE detection_jobs ADD COLUMN model TEXT NOT NULL DEFAULT 'yolo_world'")
    detection_columns = {row["name"] for row in con.execute("PRAGMA table_info(detections)")}
    if "verdict" not in detection_columns:
        con.execute("ALTER TABLE detections ADD COLUMN verdict TEXT NOT NULL DEFAULT ''")
    object_columns = {row["name"] for row in con.execute("PRAGMA table_info(objects)")}
    for column in OBJECT_TEXT_COLUMNS:
        if column not in object_columns:
            con.execute(f"ALTER TABLE objects ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
    con.commit()
    con.close()


def query(sql: str, args: tuple = ()) -> list:
    con = connect()
    try:
        return con.execute(_sql(sql), args).fetchall()
    finally:
        con.close()


def execute(sql: str, args: tuple = ()) -> int:
    con = connect()
    try:
        statement = _sql(sql)
        if DATABASE_URL.startswith("postgresql") and statement.lstrip().upper().startswith("INSERT") and "RETURNING" not in statement.upper():
            statement += " RETURNING id"
            row = con.execute(statement, args).fetchone()
            con.commit()
            return int(row["id"]) if row else 0
        cur = con.execute(statement, args)
        con.commit()
        return cur.lastrowid or cur.rowcount
    finally:
        con.close()
