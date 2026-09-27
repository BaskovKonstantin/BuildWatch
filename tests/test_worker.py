import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import db
from scripts import worker


class WorkerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        db.DB_PATH = root / "test.db"
        db.init()
        self.object_id = db.execute(
            "INSERT INTO objects(name,type) VALUES (?,?)", ("Тест", "Жильё")
        )
        self.snapshot_id = db.execute(
            "INSERT INTO snapshots(object_id,filename,src,captured_at,status,width,height)"
            " VALUES (?,?,?,?,?,?,?)",
            (self.object_id, "x.png", "uploads", "2026-06-01", "processing", 100, 80),
        )
        db.execute(
            "INSERT INTO detection_jobs(snapshot_id,model,status) VALUES (?,?,?)",
            (self.snapshot_id, "equipment", "queued"),
        )
        self.out = root / "detector"
        self.out.mkdir()
        self.script = root / "detect.py"
        self.script.touch()
        self.weights = root / "weights.pt"
        self.weights.touch()
        self.python = root / "python.exe"
        self.python.touch()
        self.old = (worker.OUT, worker.SCRIPT, worker.WEIGHTS, worker.DETECTOR_PY)
        worker.OUT, worker.SCRIPT, worker.WEIGHTS, worker.DETECTOR_PY = (
            self.out, self.script, self.weights, self.python
        )

    def tearDown(self):
        worker.OUT, worker.SCRIPT, worker.WEIGHTS, worker.DETECTOR_PY = self.old
        self.tmp.cleanup()

    def test_success_finalizes_snapshot_and_preserves_model(self):
        def run(args, **kwargs):
            payload = json.loads((self.out / f"snap_{self.snapshot_id}.in.json").read_text())
            self.assertEqual(payload["model"], "equipment")
            source = worker.ROOT / "backend" / "media" / "uploads" / "x.png"
            self.assertEqual(payload["image"], worker.runtime_path(source))
            self.assertEqual(args[0], worker.runtime_path(self.python))
            self.assertEqual(kwargs["cwd"], worker.runtime_path(worker.ROOT))
            (self.out / f"snap_{self.snapshot_id}.json").write_text(json.dumps({
                "model": "equipment", "detections": [],
            }))
            return type("Result", (), {"returncode": 0, "stdout": ""})()

        with patch("subprocess.run", side_effect=run):
            self.assertTrue(worker.run_once())
        snap = dict(db.query("SELECT status FROM snapshots WHERE id=?", (self.snapshot_id,))[0])
        job = dict(db.query("SELECT status,error FROM detection_jobs WHERE snapshot_id=?", (self.snapshot_id,))[0])
        self.assertEqual(snap["status"], "empty")
        self.assertEqual(job, {"status": "done", "error": None})

    def test_legacy_ensemble_job_runs_current_detector_once(self):
        db.execute("UPDATE detection_jobs SET model='ensemble' WHERE snapshot_id=?", (self.snapshot_id,))

        def run(args, **kwargs):
            input_data = json.loads(Path(args[2]).read_text())
            output = Path(input_data["out"])
            output.write_text(json.dumps({"model": input_data["model"], "detections": []}))
            return type("Result", (), {"returncode": 0, "stdout": ""})()

        with patch("subprocess.run", side_effect=run) as process, patch.object(
            worker, "_detector_paths", return_value=(self.script, self.weights)
        ):
            self.assertTrue(worker.run_once())
        self.assertEqual(process.call_count, 1)
        snap = dict(db.query("SELECT status FROM snapshots WHERE id=?", (self.snapshot_id,))[0])
        job = dict(db.query("SELECT status FROM detection_jobs WHERE snapshot_id=?", (self.snapshot_id,))[0])
        self.assertEqual(snap["status"], "empty")
        self.assertEqual(job["status"], "done")

    def test_final_failure_marks_snapshot_failed(self):
        failed = type("Result", (), {"returncode": 1, "stdout": "detector failed"})()
        with patch("subprocess.run", return_value=failed):
            for _ in range(3):
                self.assertTrue(worker.run_once())
        snap = dict(db.query("SELECT status FROM snapshots WHERE id=?", (self.snapshot_id,))[0])
        job = dict(db.query("SELECT status,error,attempts FROM detection_jobs WHERE snapshot_id=?", (self.snapshot_id,))[0])
        self.assertEqual(snap["status"], "failed")
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["attempts"], 3)
        self.assertIn("detector failed", job["error"])


if __name__ == "__main__":
    unittest.main()
