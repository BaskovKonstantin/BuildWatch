import json
import tempfile
import unittest
from pathlib import Path

from scripts.merge_sonnet_annotations import merge


class MergeSonnetAnnotationsTest(unittest.TestCase):
    def test_marks_merged_manifest_as_pseudo_not_ground_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.json").write_text(json.dumps({
                "image": "one.png",
                "width": 100,
                "height": 80,
                "annotation": {"objects": [{"label": "truck", "box": [1, 2, 30, 40]}]},
            }))
            output = root / "merged.json"
            result = merge(root, output)
            self.assertFalse(result["ground_truth"])
            self.assertEqual(result["images"][0]["objects"][0]["review_status"], "candidate")


if __name__ == "__main__":
    unittest.main()
