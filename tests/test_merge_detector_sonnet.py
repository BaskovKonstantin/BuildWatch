import json
import tempfile
import unittest
from pathlib import Path

from scripts.merge_detector_sonnet import merge


class MergeDetectorSonnetTest(unittest.TestCase):
    def test_marks_only_matching_boxes_as_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pseudo = root / "pseudo.json"
            pseudo.write_text(json.dumps({"images": [{
                "image": "one.png", "objects": [{"label": "excavator", "box": [0, 0, 10, 10], "needs_review": False}],
            }]}))
            report = root / "report.json"
            report.write_text(json.dumps({"results": {"yolo_world": {"detail": {"rows": [{
                "image": "one.png", "detections": [{"label": "excavator", "box": [1, 1, 9, 9], "score": 0.8}],
            }]}}}}))
            result = merge(pseudo, report, root / "out.json")
            obj = result["images"][0]["objects"][0]
            self.assertEqual(obj["review_status"], "accepted_pseudo_label")
            self.assertEqual(obj["detector_matches"][0]["model"], "yolo_world")


if __name__ == "__main__":
    unittest.main()
