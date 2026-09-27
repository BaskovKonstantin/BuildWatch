import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_coco_report import evaluate_coco


class EvaluateCocoReportTest(unittest.TestCase):
    def test_marks_classes_without_ground_truth_as_not_evaluated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coco = root / "a.json"
            coco.write_text(json.dumps({
                "images": [{"id": 1, "file_name": "one.jpg"}],
                "categories": [{"id": 1, "name": "Excavator"}],
                "annotations": [{"image_id": 1, "category_id": 1, "bbox": [0, 0, 10, 10]}],
            }))
            report = root / "r.json"
            report.write_text(json.dumps({"results": {"thalos": {"detail": {"rows": [{
                "image": "one.jpg", "detections": [{"label": "excavator", "score": 0.9, "box": [0, 0, 10, 10]}],
            }]}}}}))
            result = evaluate_coco(coco, report, "thalos")
            self.assertTrue(result["classes"]["excavator"]["evaluated"])
            self.assertFalse(result["classes"]["dump truck"]["evaluated"])
            self.assertIsNone(result["classes"]["dump truck"]["recall"])


if __name__ == "__main__":
    unittest.main()
