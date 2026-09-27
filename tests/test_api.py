import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from PIL import Image
import app as api
import db


class UploadApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        db.DB_PATH = root / "test.db"
        api.UPLOADS = root / "uploads"
        api.UPLOADS.mkdir()
        api.DETECTOR_OUT = root / "detector"
        api.DETECTOR_OUT.mkdir()
        db.init()
        self.object_id = db.execute(
            "INSERT INTO objects(name, type) VALUES (?, ?)", ("Тест", "Жильё")
        )
        self.client = TestClient(api.app)

    def tearDown(self):
        self.client.close()
        self.tmp.cleanup()

    @staticmethod
    def png() -> bytes:
        out = io.BytesIO()
        Image.new("RGB", (32, 24), "white").save(out, format="PNG")
        return out.getvalue()

    def test_rejects_unknown_object_and_bad_date(self):
        r = self.client.post("/api/objects/999/upload", files={"file": ("x.png", self.png(), "image/png")})
        self.assertEqual(r.status_code, 404)
        r = self.client.post(
            f"/api/objects/{self.object_id}/upload",
            data={"captured_at": "not-a-date"},
            files={"file": ("x.png", self.png(), "image/png")},
        )
        self.assertEqual(r.status_code, 400)

    def test_queues_selected_model_and_can_retry_failed_snapshot(self):
        created = self.client.post(
            f"/api/objects/{self.object_id}/upload",
            files={"file": ("x.png", self.png(), "image/png")},
        )
        self.assertEqual(created.status_code, 200, created.text)
        snap_id = created.json()["id"]
        # Queue behavior is independent of whether proprietary local weights are installed.
        with patch.object(api, "detector_available", return_value=True):
            queued = self.client.post(
                f"/api/snapshots/{snap_id}/detect",
                data={"model": "uisikdag"},
            )
        self.assertEqual(queued.status_code, 200, queued.text)
        self.assertEqual(queued.json()["model"], "equipment")
        job = dict(db.query("SELECT model,status FROM detection_jobs WHERE snapshot_id=?", (snap_id,))[0])
        self.assertEqual(job, {"model": "equipment", "status": "queued"})
        db.execute("UPDATE snapshots SET status='failed' WHERE id=?", (snap_id,))
        with patch.object(api, "detector_available", return_value=True):
            retried = self.client.post(
                f"/api/snapshots/{snap_id}/detect",
                data={"model": "yolo_world"},
            )
        self.assertEqual(retried.status_code, 200, retried.text)
        job = dict(db.query("SELECT model,status,attempts FROM detection_jobs WHERE snapshot_id=?", (snap_id,))[0])
        self.assertEqual(job, {"model": "equipment", "status": "queued", "attempts": 0})
        self.client.delete(f"/api/snapshots/{snap_id}")

    def test_validates_content_and_deletes_uploaded_file(self):
        bad = self.client.post(
            f"/api/objects/{self.object_id}/upload",
            files={"file": ("fake.png", b"not an image", "image/png")},
        )
        self.assertEqual(bad.status_code, 400)

        created = self.client.post(
            f"/api/objects/{self.object_id}/upload",
            data={"captured_at": "2026-09-23"},
            files={"file": ("renamed.exe", self.png(), "application/octet-stream")},
        )
        self.assertEqual(created.status_code, 200, created.text)
        snap_id = created.json()["id"]
        row = dict(db.query("SELECT * FROM snapshots WHERE id=?", (snap_id,))[0])
        path = api.snapshot_path(row)
        self.assertTrue(path.exists())
        deleted = self.client.delete(f"/api/snapshots/{snap_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()

