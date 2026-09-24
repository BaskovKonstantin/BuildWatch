import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.fetch_openimages_subset import build_openimages_subset


class OpenImagesSubsetTest(unittest.TestCase):
    def test_builds_attributed_yolo_subset_from_explicit_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "image.jpg"
            payload.write_bytes(b"image")
            annotations = root / "annotations.csv"
            annotations.write_text(
                "ImageID,Source,LabelName,Confidence,XMin,XMax,YMin,YMax\n"
                "one,xclick,/truck,1,0.1,0.5,0.2,0.6\n"
                "one,xclick,/ignored,1,0.1,0.2,0.2,0.3\n"
                "two,xclick,/dozer,1,0.2,0.6,0.1,0.9\n",
                encoding="utf-8",
            )
            images = root / "images.csv"
            images.write_text(
                "ImageID,Subset,OriginalURL,OriginalLandingURL,License,AuthorProfileURL,Author,Title,OriginalSize,OriginalMD5,Thumbnail300KURL,Rotation\n"
                f"one,train,file://{payload},https://example.test/one,https://creativecommons.org/licenses/by/2.0/,https://example.test/author,Alice,One,1,x,file://{payload},0\n"
                f"two,train,file://{payload},https://example.test/two,https://creativecommons.org/licenses/by/2.0/,https://example.test/author,Bob,Two,1,x,file://{payload},90\n",
                encoding="utf-8",
            )
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"/truck": "truck", "/dozer": "bulldozer"}), encoding="utf-8")

            result = build_openimages_subset(annotations, images, root / "out", mapping, max_images_per_class=1)

            self.assertEqual(result["images"], 1)
            self.assertEqual(result["objects"], 1)
            self.assertEqual(result["by_class"], {"truck": 1})
            self.assertEqual(result["skipped_rotated_images"], 1)
            label = next((root / "out").glob("*/labels/one.txt"))
            self.assertEqual(label.read_text(), "6 0.300000 0.400000 0.400000 0.400000\n")
            attribution = json.loads((root / "out" / "attribution.json").read_text())
            self.assertEqual(attribution["images"][0]["author"], "Alice")
            self.assertEqual(attribution["images"][0]["license"], "https://creativecommons.org/licenses/by/2.0/")

    def test_records_unavailable_source_images_without_discarding_available_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "image.jpg"
            payload.write_bytes(b"image")
            annotations = root / "annotations.csv"
            annotations.write_text(
                "ImageID,Source,LabelName,Confidence,XMin,XMax,YMin,YMax\n"
                "good,x,/truck,1,0.1,0.5,0.2,0.6\n"
                "gone,x,/dozer,1,0.1,0.5,0.2,0.6\n",
                encoding="utf-8",
            )
            images = root / "images.csv"
            images.write_text(
                "ImageID,Subset,OriginalURL,OriginalLandingURL,License,AuthorProfileURL,Author,Title,OriginalSize,OriginalMD5,Thumbnail300KURL,Rotation\n"
                f"good,train,file://{payload},https://example.test/good,CC-BY,,Alice,,1,x,file://{payload},0\n"
                "gone,train,file:///not-present.jpg,https://example.test/gone,CC-BY,,Bob,,1,x,file:///not-present.jpg,0\n",
                encoding="utf-8",
            )
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"/truck": "truck", "/dozer": "bulldozer"}), encoding="utf-8")

            result = build_openimages_subset(annotations, images, root / "out", mapping, max_images_per_class=1)

            self.assertEqual(result["images"], 1)
            self.assertEqual(result["failed_downloads"], ["gone"])
            self.assertTrue(next((root / "out").glob("*/images/good.jpg")).exists())

    def test_selects_a_deterministic_cap_per_source_class(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = root / "image.jpg"
            payload.write_bytes(b"image")
            annotations = root / "annotations.csv"
            with annotations.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=["ImageID", "Source", "LabelName", "Confidence", "XMin", "XMax", "YMin", "YMax"])
                writer.writeheader()
                for image_id in ("one", "two", "three"):
                    writer.writerow({"ImageID": image_id, "Source": "x", "LabelName": "/truck", "Confidence": "1", "XMin": "0.1", "XMax": "0.5", "YMin": "0.2", "YMax": "0.6"})
            images = root / "images.csv"
            with images.open("w", newline="", encoding="utf-8") as file:
                writer = csv.DictWriter(file, fieldnames=["ImageID", "Subset", "OriginalURL", "OriginalLandingURL", "License", "AuthorProfileURL", "Author", "Title", "OriginalSize", "OriginalMD5", "Thumbnail300KURL", "Rotation"])
                writer.writeheader()
                for image_id in ("one", "two", "three"):
                    writer.writerow({"ImageID": image_id, "Subset": "train", "OriginalURL": f"file://{payload}", "OriginalLandingURL": "https://example.test", "License": "CC-BY", "AuthorProfileURL": "", "Author": "A", "Title": "", "OriginalSize": "1", "OriginalMD5": "x", "Thumbnail300KURL": f"file://{payload}", "Rotation": "0"})
            mapping = root / "mapping.json"
            mapping.write_text(json.dumps({"/truck": "truck"}), encoding="utf-8")

            first = build_openimages_subset(annotations, images, root / "first", mapping, max_images_per_class=1)
            second = build_openimages_subset(annotations, images, root / "second", mapping, max_images_per_class=1)

            self.assertEqual(first["selected_ids"], second["selected_ids"])
            self.assertEqual(len(first["selected_ids"]), 1)


if __name__ == "__main__":
    unittest.main()
