import json
import tempfile
import unittest
from pathlib import Path

from scripts.merge_yolo_datasets import merge_yolo_datasets


class MergeYoloDatasetsTest(unittest.TestCase):
    def test_merges_ground_truth_sources_with_prefixed_filenames_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._dataset(root / "first", "excavator-source", "one.jpg", "0 0.5 0.5 0.4 0.4\n")
            second = self._dataset(root / "second", "truck source", "one.jpg", "6 0.3 0.4 0.2 0.3\n")

            result = merge_yolo_datasets([first, second], root / "merged")

            self.assertEqual(result["images"], 4)
            self.assertEqual(result["splits"], {"train": 2, "holdout": 2})
            self.assertTrue((root / "merged" / "train" / "images" / "excavator-source__one.jpg").exists())
            self.assertTrue((root / "merged" / "train" / "images" / "truck-source__one.jpg").exists())
            provenance = json.loads((root / "merged" / "sources.json").read_text())
            self.assertEqual([item["source"] for item in provenance["sources"]], ["excavator-source", "truck source"])

    def test_resumes_after_partial_merge_without_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._dataset(root / "first", "excavator-source", "one.jpg", "0 0.5 0.5 0.4 0.4\n")
            second = self._dataset(root / "second", "truck source", "one.jpg", "6 0.3 0.4 0.2 0.3\n")

            merge_yolo_datasets([first], root / "merged")
            result = merge_yolo_datasets([first, second], root / "merged")

            self.assertEqual(result["images"], 4)
            self.assertEqual(result["splits"], {"train": 2, "holdout": 2})

    def test_rejects_source_without_ground_truth_or_holdout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bad = root / "bad"
            (bad / "train" / "images").mkdir(parents=True)
            (bad / "train" / "labels").mkdir()
            (bad / "dataset.json").write_text(json.dumps({"ground_truth": False, "classes": ["truck"]}))

            with self.assertRaisesRegex(ValueError, "ground truth"):
                merge_yolo_datasets([bad], root / "merged")

    @staticmethod
    def _dataset(root: Path, source: str, image_name: str, label: str) -> Path:
        classes = ["excavator", "dump truck", "road roller", "crane manipulator", "concrete mixer", "bulldozer", "truck", "mobile crane"]
        for split in ("train", "holdout"):
            (root / split / "images").mkdir(parents=True)
            (root / split / "labels").mkdir()
            (root / split / "images" / image_name).write_bytes(b"image")
            (root / split / "labels" / "one.txt").write_text(label, encoding="utf-8")
        (root / "dataset.json").write_text(json.dumps({"source": source, "ground_truth": True, "classes": classes}), encoding="utf-8")
        return root


if __name__ == "__main__":
    unittest.main()
