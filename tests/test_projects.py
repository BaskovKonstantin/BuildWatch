import sqlite3
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
import app as api
import db
import demo_projects


class ProjectPortfolioTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.tmp.name) / "test.db"
        db.init()
        self.client = TestClient(api.app)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    def test_init_migrates_legacy_objects_table(self):
        legacy = Path(self.tmp.name) / "legacy.db"
        con = sqlite3.connect(legacy)
        con.execute("CREATE TABLE objects(id INTEGER PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL)")
        con.execute("INSERT INTO objects(name, type) VALUES ('Old', 'Жильё')")
        con.commit()
        con.close()
        db.DB_PATH = legacy
        db.init()
        row = db.query("SELECT * FROM objects")[0]
        self.assertEqual((row["district"], row["address"], row["description"]), ("", "", ""))

    def test_create_object_stores_location_and_rejects_blank_name(self):
        r = self.client.post("/api/objects", data={
            "name": " Школа ", "type": "Образование", "district": "ЮАО", "address": "ул. Тестовая, 1",
        })
        self.assertEqual(r.status_code, 200)
        obj = db.query("SELECT * FROM objects WHERE id=?", (r.json()["id"],))[0]
        self.assertEqual((obj["name"], obj["type"], obj["district"]), ("Школа", "Образование", "ЮАО"))
        self.assertEqual(self.client.post("/api/objects", data={"name": "  "}).status_code, 422)

    def test_list_objects_returns_portfolio_summary(self):
        oid = db.execute("INSERT INTO objects(name, type) VALUES ('P', 'Жильё')")
        for pos, (kind, dfrom, dto) in enumerate([
            ("ground", "2000-01-01", "2000-12-31"),
            ("frame", "2001-01-01", "2099-12-31"),
        ]):
            db.execute(
                "INSERT INTO stages(object_id, position, kind, name, date_from, date_to, status)"
                " VALUES (?,?,?,?,?,?,?)", (oid, pos, kind, kind, dfrom, dto, "current"))
        sid = db.execute(
            "INSERT INTO snapshots(object_id, filename, src, captured_at, status, width, height)"
            " VALUES (?,?,?,?,?,?,?)", (oid, "x.png", "uploads", "2001-02-01", "detected", 10, 10))
        for label, score in [("tower crane", 0.9), ("worker", 0.9), ("truck", 0.2)]:
            db.execute(
                "INSERT INTO detections(snapshot_id, model, label, score, x1, y1, x2, y2)"
                " VALUES (?,?,?,?,0,0,5,5)", (sid, "yolo_world", label, score))
        item = self.client.get("/api/objects").json()[0]
        self.assertEqual(item["stage"]["name"], "frame")
        self.assertEqual(item["stage"]["position"], 2)
        self.assertEqual(item["stages_total"], 2)
        self.assertEqual(item["planned_finish"], "2099-12-31")
        self.assertEqual(item["last_snapshot"], "2001-02-01")
        self.assertEqual(item["equipment"], ["tower crane"])  # PPE and low-score dropped
        self.assertTrue(0 < item["progress"] < 1)
        detail = self.client.get(f"/api/objects/{oid}").json()
        self.assertEqual(detail["summary"]["stage"]["name"], "frame")

    def test_demo_projects_move_samples_and_keep_uploads(self):
        first = db.execute("INSERT INTO objects(name, type) VALUES (?, 'Жильё')",
                           (demo_projects.PROJECTS[0]["name"],))
        moved = db.execute(
            "INSERT INTO snapshots(object_id, filename, src, captured_at, status, width, height)"
            " VALUES (?,?,?,?,?,?,?)", (first, "Screenshot_2.png", "samples", "2026-01-01", "detected", 10, 10))
        db.execute("INSERT INTO detections(snapshot_id, model, label, score, x1, y1, x2, y2)"
                   " VALUES (?,?,?,?,0,0,5,5)", (moved, "yolo_world", "truck", 0.8))
        upload = db.execute(
            "INSERT INTO snapshots(object_id, filename, src, captured_at, status, width, height)"
            " VALUES (?,?,?,?,?,?,?)", (first, "up.png", "uploads", "2026-07-14", "detected", 10, 10))
        con = db.connect()
        ids = demo_projects.apply(con, date(2026, 9, 26).isoformat())
        con.commit()
        con.close()
        self.assertEqual(len(db.query("SELECT id FROM objects")), len(demo_projects.PROJECTS))
        school = db.query("SELECT id FROM objects WHERE name='Школа на 1 100 мест'")[0]["id"]
        snap = db.query("SELECT * FROM snapshots WHERE id=?", (moved,))[0]
        self.assertEqual((snap["object_id"], snap["captured_at"]), (school, "2026-09-18"))
        self.assertEqual(len(db.query("SELECT id FROM detections WHERE snapshot_id=?", (moved,))), 1)
        self.assertEqual(db.query("SELECT object_id FROM snapshots WHERE id=?", (upload,))[0]["object_id"], first)
        self.assertIn(school, ids)
        statuses = [r["status"] for r in db.query(
            "SELECT status FROM stages WHERE object_id=? ORDER BY position", (school,))]
        self.assertEqual(statuses, ["done", "done", "current", "future", "future"])
        # Idempotent: a second run does not duplicate projects or stages.
        con = db.connect()
        demo_projects.apply(con, "2026-09-26")
        con.commit()
        con.close()
        self.assertEqual(len(db.query("SELECT id FROM objects")), len(demo_projects.PROJECTS))
        self.assertEqual(len(db.query("SELECT id FROM stages WHERE object_id=?", (school,))), 5)


if __name__ == "__main__":
    unittest.main()
