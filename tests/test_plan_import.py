import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from openpyxl import Workbook
import app as api
import db


class PlanImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp.name) / "plan.db"
        db.init()
        self.object_id = db.execute("INSERT INTO objects(name,type) VALUES (?,?)", ("Школа", "Образование"))
        self.client = TestClient(api.app)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_csv_preview_does_not_change_plan(self):
        csv_data = "Этап;Дата начала;Дата окончания\nУстройство котлована;01.10.2026;31.10.2026\nМонолит;01.11.2026;bad\n".encode("utf-8-sig")
        res = self.client.post(f"/api/objects/{self.object_id}/plan/preview",
                               files={"file": ("plan.csv", csv_data, "text/csv")})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["stages"][0]["kind"], "excavation")
        self.assertEqual(res.json()["stages"][0]["date_from"], "2026-10-01")
        self.assertEqual(len(res.json()["issues"]), 1)
        self.assertEqual(db.query("SELECT COUNT(*) AS n FROM stages")[0]["n"], 0)

    def test_xlsx_preview_and_undated_catalog_rejection(self):
        book = Workbook()
        sheet = book.active
        sheet.append(["Этап", "Дата начала", "Дата окончания"])
        sheet.append(["Монолитный каркас", "2026-09-01", "2026-12-01"])
        output = io.BytesIO()
        book.save(output)
        res = self.client.post(f"/api/objects/{self.object_id}/plan/preview",
                               files={"file": ("plan.xlsx", output.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["stages"][0]["kind"], "frame")
        invalid = self.client.post(f"/api/objects/{self.object_id}/plan/preview",
                                   files={"file": ("catalog.csv", "Вид работ;Жильё\nКотлован;да".encode(), "text/csv")})
        self.assertEqual(invalid.status_code, 422)

    def test_corrupt_xlsx_returns_readable_error(self):
        res = self.client.post(f"/api/objects/{self.object_id}/plan/preview",
                               files={"file": ("plan.xlsx", b"not a workbook", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"], "Не удалось прочитать таблицу")


if __name__ == "__main__":
    unittest.main()
