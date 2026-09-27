import json
import tempfile
import unittest
from pathlib import Path

from backend.detector_config import canonical_model, model_config, to_detector_path
from backend import db


class DetectorConfigTest(unittest.TestCase):
    def test_converts_wsl_mount_to_windows_path(self):
        self.assertEqual(
            to_detector_path(Path("/mnt/d/Projects/BuildWatch/image.png")),
            r"D:\Projects\BuildWatch\image.png",
        )

    def test_keeps_native_path_and_rejects_unknown_model(self):
        self.assertEqual(to_detector_path(Path(r"D:\image.png")), r"D:\image.png")
        self.assertEqual(canonical_model("YOLO-World"), "equipment")
        self.assertEqual(model_config("uisikdag").name, "equipment")
        with self.assertRaises(ValueError):
            model_config("unknown")


class DetectionServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.tmp.name) / "test.db"
        db.init()
        self.object_id = db.execute(
            "INSERT INTO objects(name,type) VALUES (?,?)", ("Тест", "Жильё")
        )
        db.execute(
            "INSERT INTO stages(object_id,position,kind,name,date_from,date_to,status)"
            " VALUES (?,?,?,?,?,?,?)",
            (self.object_id, 0, "ground", "Подготовка", "2026-01-01", "2026-12-31", "current"),
        )
        self.snapshot_id = db.execute(
            "INSERT INTO snapshots(object_id,filename,src,captured_at,status,width,height)"
            " VALUES (?,?,?,?,?,?,?)",
            (self.object_id, "x.png", "uploads", "2026-06-01", "processing", 100, 80),
        )
        db.execute(
            "INSERT INTO detection_jobs(snapshot_id,model,status) VALUES (?,?,?)",
            (self.snapshot_id, "uisikdag", "running"),
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_finalizes_result_with_declared_model_and_completes_job(self):
        from backend.detection_service import finalize_detection

        out_dir = Path(self.tmp.name) / "detector"
        out_dir.mkdir()
        result = out_dir / f"snap_{self.snapshot_id}.json"
        result.write_text(json.dumps({
            "model": "uisikdag",
            "detections": [{"label": "loader", "score": 0.8, "box": [1, 2, 30, 40]}],
        }), encoding="utf-8")

        self.assertTrue(finalize_detection(self.snapshot_id, out_dir))
        snap = dict(db.query("SELECT status FROM snapshots WHERE id=?", (self.snapshot_id,))[0])
        job = dict(db.query("SELECT status FROM detection_jobs WHERE snapshot_id=?", (self.snapshot_id,))[0])
        det = dict(db.query("SELECT model,label FROM detections WHERE snapshot_id=?", (self.snapshot_id,))[0])
        self.assertEqual(snap["status"], "detected")
        self.assertEqual(job["status"], "done")
        self.assertEqual(det, {"model": "equipment", "label": "loader"})
        self.assertFalse(result.exists())


if __name__ == "__main__":
    unittest.main()
