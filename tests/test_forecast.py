import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import forecast


def _card(snapshots, stages, warnings=None):
    return {"object": {"type": "Жильё"}, "stages": stages, "snapshots": snapshots, "warnings": warnings or []}


def _stage(name, kind, start, end):
    return {"id": name, "name": name, "kind": kind, "date_from": start, "date_to": end, "status": "current"}


def _snap(snap_id, captured, label="excavator", box=(0, 0, 10, 10)):
    x1, y1, x2, y2 = box
    return {
        "id": snap_id, "captured_at": captured, "status": "detected", "width": 100, "height": 100,
        "detections": [{"label": label, "score": 0.9, "verdict": "", "x1": x1, "y1": y1, "x2": x2, "y2": y2}],
    }


class ForecastTest(unittest.TestCase):
    def test_stuck_series_is_behind_plan(self):
        stages = [
            _stage("Котлован", "excavation", "2026-01-01", "2026-06-30"),
            _stage("Каркас", "frame", "2026-07-01", "2026-12-31"),
        ]
        snaps = [_snap(1, "2026-06-01"), _snap(2, "2026-06-20")]
        result = forecast.forecast_schedule(_card(snaps, stages), "2026-08-01")
        self.assertEqual(result["verdict"], "behind")
        self.assertEqual(result["pace_label"], "этап не сдвинулся")
        self.assertGreater(result["days_delta"], 0)
        self.assertIn("видимой части", result["disclaimer"])
        self.assertTrue(any(row["name"] == "кран" and row["missing"] for row in result["equipment_gap"]["rows"]))

    def test_one_snapshot_is_unknown(self):
        stages = [_stage("Котлован", "excavation", "2026-01-01", "2026-12-31")]
        result = forecast.forecast_schedule(_card([_snap(1, "2026-06-01")], stages), "2026-08-01")
        self.assertEqual(result["verdict"], "unknown")
        self.assertIsNone(result["days_delta"])
        self.assertEqual(result["activity"]["verdict"], "insufficient")

    def test_open_rules_add_penalty_days(self):
        stages = [_stage("Котлован", "excavation", "2026-01-01", "2026-12-31")]
        snaps = [_snap(1, "2026-06-01", box=(0, 0, 10, 10)), _snap(2, "2026-07-01", box=(70, 70, 90, 90))]
        warnings = [
            {"rule": "R-03", "status": "open", "severity": "review"},
            {"rule": "R-01", "status": "open", "severity": "violation"},
            {"rule": "R-02", "status": "open", "severity": "review"},
        ]
        result = forecast.forecast_schedule(_card(snaps, stages, warnings), "2026-08-01")
        self.assertEqual(result["days_delta"], 1)
        self.assertEqual(result["verdict"], "behind")
        self.assertEqual(result["activity"]["verdict"], "working")

    def test_dynamics_sentence_counts_repeated_rules(self):
        stages = [_stage("Котлован", "excavation", "2026-01-01", "2026-12-31")]
        snaps = [_snap(1, "2026-08-01"), _snap(2, "2026-08-10"), _snap(3, "2026-08-20")]
        warnings = [
            {"rule": "R-03", "status": "open", "severity": "review", "captured_at": "2026-08-01"},
            {"rule": "R-03", "status": "open", "severity": "review", "captured_at": "2026-08-10"},
        ]
        dynamics = forecast.build_dynamics(_card(snaps, stages, warnings), "2026-08-25")
        self.assertIn("3 снимка", dynamics["sentence"])
        self.assertIn("этап не менялся", dynamics["sentence"])
        self.assertIn("1 нарушение повторяется", dynamics["sentence"])
        self.assertGreaterEqual(len(dynamics["points"]), 1)

    def test_quality_uses_inspector_verdicts_only(self):
        snap = _snap(1, "2026-08-01")
        snap["detections"].append({"label": "truck", "score": 0.8, "verdict": "correct", "x1": 0, "y1": 0, "x2": 1, "y2": 1})
        snap["detections"].append({"label": "loader", "score": 0.8, "verdict": "wrong", "x1": 0, "y1": 0, "x2": 1, "y2": 1})
        quality = forecast.recognition_quality(_card([snap], []))
        self.assertEqual((quality["correct"], quality["wrong"], quality["pending"]), (1, 1, 1))
        self.assertEqual(quality["correct_share"], 0.5)
        self.assertIn("не метрика", quality["note"])


if __name__ == "__main__":
    unittest.main()
