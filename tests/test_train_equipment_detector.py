import json
import tempfile
import unittest
from pathlib import Path

from scripts.train_equipment_detector import prepare_dataset


class TrainingPreparationTest(unittest.TestCase):
    def test_refuses_pseudo_dataset_without_explicit_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset"
            (dataset / "train" / "images").mkdir(parents=True)
            (dataset / "train" / "labels").mkdir()
            (dataset / "holdout" / "images").mkdir(parents=True)
            (dataset / "holdout" / "labels").mkdir()
            (dataset / "dataset.json").write_text(json.dumps({
                "ground_truth": False,
                "classes": ["truck"],
            }))
            with self.assertRaises(ValueError):
                prepare_dataset(dataset, root / "out", allow_pseudo=False)

    def test_accepts_official_validation_split_for_ground_truth_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset"
            for split in ("train", "val"):
                (dataset / split / "images").mkdir(parents=True)
                (dataset / split / "labels").mkdir()
            (dataset / "dataset.json").write_text(json.dumps({
                "ground_truth": True,
                "classes": ["excavator"],
            }))

            yaml_path = prepare_dataset(dataset, root / "out", allow_pseudo=False)

            self.assertIn("val: val/images", yaml_path.read_text())

    def test_writes_ultralytics_yaml_for_explicit_experiment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = root / "dataset"
            (dataset / "train" / "images").mkdir(parents=True)
            (dataset / "train" / "labels").mkdir()
            (dataset / "holdout" / "images").mkdir(parents=True)
            (dataset / "holdout" / "labels").mkdir()
            (dataset / "dataset.json").write_text(json.dumps({
                "ground_truth": False,
                "classes": ["truck"],
            }))
            yaml_path = prepare_dataset(dataset, root / "out", allow_pseudo=True)
            text = yaml_path.read_text()
            self.assertIn("names:", text)
            self.assertIn("truck", text)
            self.assertIn("train:", text)
            self.assertIn("val:", text)


if __name__ == "__main__":
    unittest.main()
