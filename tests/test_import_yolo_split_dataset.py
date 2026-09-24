import json
import tempfile
import unittest
from pathlib import Path

from scripts.import_yolo_split_dataset import import_yolo_split_dataset


class YoloSplitImportTest(unittest.TestCase):
    def test_remaps_ids_and_preserves_official_split_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for split in ("train", "valid"):
                (root / split / "images").mkdir(parents=True)
                (root / split / "labels").mkdir()
                (root / split / "images" / "photo.jpg").write_bytes(b"image")
                (root / split / "labels" / "photo.txt").write_text("0 0.5 0.5 0.4 0.4\n1 0.2 0.2 0.1 0.1\n", encoding="utf-8")
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"0": "dump truck", "1": None}), encoding="utf-8")

            result = import_yolo_split_dataset(
                root, root / "out", mapping, "kaggle-construction-equipment",
                "research-only", "https://www.kaggle.com/datasets/xyzyxzzxy/construction-equipment",
                "sha256:test", train_split="train", holdout_split="valid",
            )

            self.assertEqual(result["images"], 2)
            self.assertEqual(result["objects"], 2)
            self.assertEqual(result["by_class"], {"dump truck": 2})
            self.assertEqual(result["splits"], {"train": 1, "holdout": 1})
            self.assertEqual((root / "out" / "train" / "labels" / "photo.txt").read_text(), "1 0.500000 0.500000 0.400000 0.400000\n")
            metadata = json.loads((root / "out" / "dataset.json").read_text())
            self.assertTrue(metadata["ground_truth"])
            self.assertEqual(metadata["archive_sha256"], "sha256:test")

    def test_rejects_undeclared_class_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for split in ("train", "valid"):
                (root / split / "images").mkdir(parents=True)
                (root / split / "labels").mkdir()
                (root / split / "images" / "photo.jpg").write_bytes(b"image")
                (root / split / "labels" / "photo.txt").write_text("5 0.5 0.5 0.4 0.4\n", encoding="utf-8")
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"0": "dump truck"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "undeclared source class 5"):
                import_yolo_split_dataset(
                    root, root / "out", mapping, "source", "research-only", "https://example.test", "sha", "train", "valid",
                )


if __name__ == "__main__":
    unittest.main()
