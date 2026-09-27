import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_detectors import evaluate, load_annotations, load_predictions


class DetectorEvaluationTest(unittest.TestCase):
    def test_matches_boxes_per_class_and_reports_false_positives(self):
        annotations = {"one.png": [{"label": "excavator", "box": [0, 0, 10, 10]}]}
        predictions = {
            "one.png": [
                {"label": "excavator", "score": 0.9, "box": [1, 1, 9, 9]},
                {"label": "truck", "score": 0.8, "box": [20, 20, 30, 30]},
            ]
        }
        result = evaluate(annotations, predictions, threshold=0.35, iou_threshold=0.5)
        self.assertEqual(result["classes"]["excavator"]["tp"], 1)
        self.assertEqual(result["classes"]["truck"]["fp"], 1)
        self.assertEqual(result["micro"]["precision"], 0.5)

    def test_loads_existing_compare_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps({
                "results": {"yolo_world": {
                    "summary": {"per_image_s": 0.1},
                    "detail": {"rows": [{"image": "one.png", "detections": []}]},
                }},
            }))
            predictions, latency = load_predictions(path, "yolo_world")
            self.assertEqual(predictions, {"one.png": []})
            self.assertEqual(latency, 0.1)


if __name__ == "__main__":
    unittest.main()
