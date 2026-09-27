import json
import tempfile
import unittest
from pathlib import Path

from scripts.import_external_dataset import import_coco


class ExternalDatasetImportTest(unittest.TestCase):
    def test_maps_coco_categories_and_preserves_source_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = root / "images"
            images.mkdir()
            (images / "one.png").write_bytes(b"image")
            coco = root / "annotations.json"
            coco.write_text(json.dumps({
                "images": [{"id": 1, "file_name": "one.png", "width": 100, "height": 80}],
                "categories": [{"id": 1, "name": "Dump truck"}, {"id": 2, "name": "Tower crane"}],
                "annotations": [
                    {"id": 1, "image_id": 1, "category_id": 1, "bbox": [10, 20, 40, 30]},
                    {"id": 2, "image_id": 1, "category_id": 2, "bbox": [1, 2, 3, 4]},
                ],
            }))
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"dump truck": "dump truck", "tower crane": None}))
            result = import_coco(coco, images, root / "out", mapping, "acid", "research-only", holdout=0)
            self.assertEqual(result["objects"], 1)
            self.assertEqual(result["source"], "acid")
            labels = (root / "out" / "train" / "labels" / "one.txt").read_text().split()
            self.assertEqual(labels[0], "1")


if __name__ == "__main__":
    unittest.main()
