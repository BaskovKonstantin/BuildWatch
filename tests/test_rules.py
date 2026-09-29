import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import rules


def stage(kind="excavation"):
    return [{"kind": kind, "name": "Устройство котлована", "date_from": "2026-01-01", "date_to": "2026-12-31", "status": "current"}]


class RulesTest(unittest.TestCase):
    def snap(self, status="detected"):
        return {"id": 1, "captured_at": "2026-06-01", "status": status}

    def det(self, label, score=.8):
        return {"label": label, "score": score, "x1": 0, "y1": 0, "x2": 10, "y2": 10}

    def test_missing_required_equipment(self):
        warnings = rules.evaluate_snapshot(self.snap(), [self.det("excavator")], stage())
        self.assertTrue(any(w["rule"] == "R-03" and "самосвал" in w["body"] for w in warnings))

    def test_loader_is_not_normalized_to_bulldozer(self):
        self.assertEqual(rules.normalize_label("Loader"), "loader")

    def test_no_absence_warning_before_detection(self):
        warnings = rules.evaluate_snapshot(self.snap("processing"), [], stage())
        self.assertFalse(any(w["rule"] == "R-03" for w in warnings))

    def test_complete_stage_has_no_missing_warning(self):
        detections = [self.det("excavator"), self.det("dump truck")]
        warnings = rules.evaluate_snapshot(self.snap(), detections, stage())
        self.assertFalse(any(w["rule"] == "R-03" for w in warnings))

    def test_alternative_crane_satisfies_frame_requirement(self):
        detections = [self.det("mobile crane"), self.det("concrete pump")]
        warnings = rules.evaluate_snapshot(self.snap(), detections, stage("frame"))
        self.assertFalse(any(w["rule"] == "R-03" for w in warnings))

    def test_low_confidence_stage_mismatch_requires_review(self):
        stages = stage("facade")
        self.assertEqual(rules.detection_match(self.det("truck crane", .21), stages, "2026-06-01"), "review")
        self.assertEqual(rules.detection_match(self.det("truck crane", .8), stages, "2026-06-01"), "mismatch")

    def test_overlapping_boxes_from_two_models_form_one_group(self):
        detections = [
            {**self.det("excavator", .8), "model": "yolo_world"},
            {**self.det("loader", .7), "x1": 1, "y1": 1, "x2": 9, "y2": 9, "model": "uisikdag"},
        ]
        self.assertEqual(len(rules.group_detections(detections)), 1)

    def test_stationary_equipment_raises_activity_question(self):
        first = {"id": 1, "captured_at": "2026-06-01", "status": "detected", "width": 100, "height": 100,
                 "detections": [self.det("excavator")]}
        second = {"id": 2, "captured_at": "2026-06-08", "status": "detected", "width": 100, "height": 100,
                  "detections": [self.det("excavator")]}
        warnings = rules.evaluate_series([second, first])
        self.assertEqual(warnings[0]["rule"], "R-08")
        self.assertEqual(warnings[0]["severity"], "review")
        self.assertEqual(warnings[0]["snapshot_id"], 2)

    def test_moved_equipment_is_not_idle(self):
        first = {"id": 1, "captured_at": "2026-06-01", "status": "detected", "width": 100, "height": 100,
                 "detections": [self.det("excavator")]}
        second = {"id": 2, "captured_at": "2026-06-08", "status": "detected", "width": 100, "height": 100,
                  "detections": [{**self.det("excavator"), "x1": 60, "y1": 60, "x2": 90, "y2": 90}]}
        self.assertEqual(rules.evaluate_series([first, second]), [])
        self.assertEqual(rules.series_motion([first, second])["verdict"], "working")

    def test_danger_zone_and_crane_storage(self):
        snap = {**self.snap(), "width": 100, "height": 100}
        danger = {"kind": "danger", "name": "Опасная зона", "polygon": [[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]]}
        storage = {"kind": "storage", "name": "Склад", "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]}
        warnings = rules.evaluate_snapshot(snap, [self.det("excavator")], stage(), zones=[danger])
        self.assertTrue(any(w["rule"] == "R-09" and w["severity"] == "violation" for w in warnings))
        mounting = [{"kind": "frame", "name": "Монолитный каркас", "date_from": "2026-01-01", "date_to": "2026-12-31", "status": "current"}]
        crane = {**self.det("tower crane"), "x1": 10, "y1": 10, "x2": 40, "y2": 40}
        stored = rules.evaluate_snapshot(snap, [crane], mounting, zones=[storage])
        self.assertTrue(any(w["rule"] == "R-10" and w["severity"] == "review" for w in stored))
        excavation = rules.evaluate_snapshot(snap, [crane], stage(), zones=[storage])
        self.assertFalse(any(w["rule"] == "R-10" for w in excavation))


if __name__ == "__main__":
    unittest.main()
