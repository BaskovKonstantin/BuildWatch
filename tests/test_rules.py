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



if __name__ == "__main__":
    unittest.main()
