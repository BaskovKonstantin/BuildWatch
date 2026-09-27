import json
import unittest

from scripts.sonnet_annotate import extract_json, validate_annotation


class SonnetAnnotationTest(unittest.TestCase):
    def test_extracts_json_from_markdown_fence(self):
        payload = extract_json('```json\n{"objects": []}\n```')
        self.assertEqual(payload, {"objects": []})

    def test_validates_and_clips_boxes_to_image(self):
        result = validate_annotation({
            "objects": [{
                "label": "dump truck",
                "box": [-2, 4, 120, 70],
                "visibility": "clear",
                "needs_review": False,
            }],
        }, width=100, height=60)
        self.assertEqual(result["objects"][0]["box"], [0, 4, 100, 60])
        self.assertEqual(result["objects"][0]["label"], "dump truck")

    def test_rejects_unknown_class_and_invalid_box(self):
        with self.assertRaises(ValueError):
            validate_annotation({"objects": [{"label": "house", "box": [0, 0, 5, 5]}]}, 10, 10)
        with self.assertRaises(ValueError):
            validate_annotation({"objects": [{"label": "truck", "box": [5, 5, 2, 2]}]}, 10, 10)


if __name__ == "__main__":
    unittest.main()
