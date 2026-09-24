import json
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_mocs import prepare_coco_split, prepare_test_split, write_dataset_manifest


class MocsPreparationTest(unittest.TestCase):
    def test_converts_coco_split_and_reports_ignored_classes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = root / "images"
            images.mkdir()
            (images / "one.jpg").write_bytes(b"one")
            (images / "empty.jpg").write_bytes(b"empty")
            annotations = root / "annotations.json"
            annotations.write_text(json.dumps({
                "images": [
                    {"id": 1, "file_name": "one.jpg", "width": 100, "height": 80},
                    {"id": 2, "file_name": "empty.jpg", "width": 100, "height": 80},
                ],
                "categories": [
                    {"id": 1, "name": "Excavator"},
                    {"id": 2, "name": "Worker"},
                ],
                "annotations": [
                    {"id": 1, "image_id": 1, "category_id": 1, "bbox": [10, 20, 40, 30]},
                    {"id": 2, "image_id": 1, "category_id": 2, "bbox": [1, 2, 3, 4]},
                ],
            }), encoding="utf-8")
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"excavator": "excavator", "worker": None}), encoding="utf-8")

            result = prepare_coco_split(annotations, images, root / "out", mapping, "val")

            self.assertEqual(result["images"], 2)
            self.assertEqual(result["source_annotations"], 2)
            self.assertEqual(result["mapped_objects"], 1)
            self.assertEqual(result["ignored_objects"], 1)
            self.assertEqual((root / "out" / "val" / "labels" / "one.txt").read_text(), "0 0.300000 0.437500 0.400000 0.375000\n")
            self.assertEqual((root / "out" / "val" / "labels" / "empty.txt").read_text(), "")
            self.assertTrue((root / "out" / "val" / "images" / "one.jpg").exists())

    def test_clips_boxes_that_extend_past_image_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = root / "images"
            images.mkdir()
            (images / "edge.jpg").write_bytes(b"edge")
            annotations = root / "annotations.json"
            annotations.write_text(json.dumps({
                "images": [{"id": 1, "file_name": "edge.jpg", "width": 100, "height": 80}],
                "categories": [{"id": 1, "name": "Excavator"}],
                "annotations": [{"id": 1, "image_id": 1, "category_id": 1, "bbox": [90, 70, 20, 20]}],
            }), encoding="utf-8")
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"excavator": "excavator"}), encoding="utf-8")

            prepare_coco_split(annotations, images, root / "out", mapping, "val")

            self.assertEqual(
                (root / "out" / "val" / "labels" / "edge.txt").read_text(),
                "0 0.950000 0.937500 0.100000 0.125000\n",
            )

    def test_prepares_test_images_without_annotations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            images = root / "images"
            images.mkdir()
            (images / "test.jpg").write_bytes(b"test")
            image_info = root / "image_info_test.json"
            image_info.write_text(json.dumps({
                "images": [{"id": 1, "file_name": "test.jpg", "width": 100, "height": 80}]
            }), encoding="utf-8")

            result = prepare_test_split(image_info, images, root / "out")

            self.assertEqual(result["images"], 1)
            self.assertEqual(result["annotations"], 0)
            self.assertTrue((root / "out" / "test" / "images" / "test.jpg").exists())
            self.assertEqual((root / "out" / "test" / "labels" / "test.txt").read_text(), "")

    def test_writes_training_manifest_for_prepared_splits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = write_dataset_manifest(root, [{
                "split": "train",
                "ground_truth": True,
                "classes": ["excavator"],
                "images": 10,
            }])

            self.assertEqual(manifest["ground_truth"], True)
            self.assertEqual(manifest["splits"], ["train"])
            self.assertEqual(json.loads((root / "dataset.json").read_text())["images"], 10)

    def test_rejects_missing_image_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            annotations = root / "annotations.json"
            annotations.write_text(json.dumps({"images": [], "categories": [], "annotations": []}), encoding="utf-8")
            mapping = root / "mapping.json"
            mapping.write_text("{}", encoding="utf-8")

            with self.assertRaises(FileNotFoundError):
                prepare_coco_split(annotations, root / "missing", root / "out", mapping, "train")


if __name__ == "__main__":
    unittest.main()
