import json
import tempfile
import unittest
from pathlib import Path

from scripts.import_yolo_dataset import import_yolo_dataset


class YoloDatasetImportTest(unittest.TestCase):
    def test_remaps_labels_splits_deterministically_and_records_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "one.jpg").write_bytes(b"one")
            (source / "one.txt").write_text("0 0.5 0.5 0.4 0.4\n", encoding="utf-8")
            (source / "two.jpg").write_bytes(b"two")
            (source / "two.txt").write_text("0 0.2 0.3 0.1 0.2\n", encoding="utf-8")
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"0": "excavator"}), encoding="utf-8")

            result = import_yolo_dataset(
                source, root / "out", mapping, "github-construction-machines",
                "research-only", "https://example.test/source.zip", "abc123", holdout=0,
            )

            self.assertEqual(result["images"], 2)
            self.assertEqual(result["objects"], 2)
            self.assertEqual(result["by_class"], {"excavator": 2})
            self.assertEqual(result["archive_sha256"], "abc123")
            self.assertEqual((root / "out" / "train" / "labels" / "one.txt").read_text(), "0 0.500000 0.500000 0.400000 0.400000\n")
            metadata = json.loads((root / "out" / "dataset.json").read_text(encoding="utf-8"))
            self.assertTrue(metadata["ground_truth"])
            self.assertEqual(metadata["source_url"], "https://example.test/source.zip")

    def test_clips_source_boxes_that_cross_image_boundaries_and_records_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "edge.jpg").write_bytes(b"edge")
            (source / "edge.txt").write_text("0 0.009 0.607984 0.062 0.286592\n", encoding="utf-8")
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"0": "excavator"}), encoding="utf-8")

            result = import_yolo_dataset(
                source, root / "out", mapping, "source", "research-only",
                "https://example.test", "hash", holdout=0,
            )

            self.assertEqual(result["clipped_objects"], 1)
            self.assertEqual(
                (root / "out" / "train" / "labels" / "edge.txt").read_text(),
                "0 0.020000 0.607984 0.040000 0.286592\n",
            )

    def test_rejects_empty_source_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"0": "excavator"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "no supported image files"):
                import_yolo_dataset(
                    source, root / "out", mapping, "source", "research-only",
                    "https://example.test", "hash", holdout=0,
                )

    def test_rejects_undeclared_or_invalid_source_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "bad.jpg").write_bytes(b"bad")
            (source / "bad.txt").write_text("1 1.1 0.5 0.4 0.4\n", encoding="utf-8")
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"0": "excavator"}), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "bad.txt:1"):
                import_yolo_dataset(
                    source, root / "out", mapping, "source", "research-only",
                    "https://example.test", "hash", holdout=0,
                )


if __name__ == "__main__":
    unittest.main()
