import json
import tempfile
import unittest
from pathlib import Path

from scripts.export_reviewed_dataset import export_dataset


class ExportReviewedDatasetTest(unittest.TestCase):
    def test_exports_only_verified_objects_to_coco_and_yolo(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = root / "images"
            images.mkdir()
            (images / "one.png").write_bytes(b"fake")
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({
                "images": [{
                    "image": "one.png", "width": 100, "height": 80,
                    "objects": [
                        {"label": "truck", "box": [10, 20, 50, 60], "review_status": "vlm_verified"},
                        {"label": "excavator", "box": [1, 2, 3, 4], "review_status": "manual_review"},
                    ],
                }],
            }))
            output = root / "dataset"
            result = export_dataset(manifest, images, output, holdout_fraction=0)
            self.assertEqual(result["objects"], 1)
            coco = json.loads((output / "annotations.coco.json").read_text())
            self.assertEqual(len(coco["annotations"]), 1)
            self.assertTrue((output / "train" / "images" / "one.png").exists())
            label = (output / "train" / "labels" / "one.txt").read_text().strip().split()
            self.assertEqual(label[0], "6")


if __name__ == "__main__":
    unittest.main()
