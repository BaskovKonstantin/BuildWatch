import json
import tempfile
import unittest
from pathlib import Path

from scripts.apply_sonnet_reviews import apply_reviews
from scripts.sonnet_review import validate_review


class SonnetReviewTest(unittest.TestCase):
    def test_validates_accept_and_correction_decisions(self):
        accepted = validate_review({"decision": "accept", "label": "excavator", "reason": "clear"})
        corrected = validate_review({"decision": "correct", "label": "dump truck", "reason": "tipper body"})
        self.assertEqual(accepted["decision"], "accept")
        self.assertEqual(corrected["label"], "dump truck")

    def test_rejects_invalid_decision_or_class(self):
        with self.assertRaises(ValueError):
            validate_review({"decision": "accept", "label": "house"})
        with self.assertRaises(ValueError):
            validate_review({"decision": "unknown", "label": "truck"})

    def test_applies_review_without_marking_ground_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "ground_truth": False,
                "images": [{"image": "one.png", "objects": [
                    {"label": "truck", "box": [1, 2, 10, 12], "review_status": "disagreement"}
                ]}],
            }))
            reviews = root / "reviews"
            reviews.mkdir()
            (reviews / "one.json").write_text(json.dumps({
                "image": "one.png",
                "reviews": [{"object_index": 0, "decision": "correct", "label": "dump truck", "reason": "tipper"}],
            }))
            output = root / "out.json"
            result = apply_reviews(manifest, reviews, output)
            obj = result["images"][0]["objects"][0]
            self.assertFalse(result["ground_truth"])
            self.assertEqual(obj["label"], "dump truck")
            self.assertEqual(obj["review_status"], "vlm_verified")


if __name__ == "__main__":
    unittest.main()
