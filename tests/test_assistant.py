import sys
import tempfile
import unittest
import json
from os import environ
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
import app as api
import assistant_service
import db


class AssistantApiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        db.DB_PATH = Path(self.temp.name) / "assistant.db"
        db.init()
        self.object_id = db.execute("INSERT INTO objects(name,type) VALUES (?,?)", ("Школа №1", "Образование"))
        self.stage_id = db.execute(
            "INSERT INTO stages(object_id,position,kind,name,date_from,date_to,status) VALUES (?,?,?,?,?,?,?)",
            (self.object_id, 0, "excavation", "Котлован", "2026-09-01", "2026-09-30", "current"),
        )
        self.client = TestClient(api.app)

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def test_answer_uses_only_real_evidence(self):
        with patch("assistant_service.zen_access", return_value=("test-key", "https://example.invalid")), patch(
            "assistant_service._ask_zen",
            return_value={"answer": "Этап котлована запланирован на сентябрь.",
                          "evidence": [f"object:{self.object_id}", "warning:999"], "action": None},
        ):
            res = self.client.post("/api/assistant/query", json={"message": "Какой этап?", "object_id": self.object_id})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["evidence"], [{"label": "Школа №1", "url": f"/objects/{self.object_id}"}])
        self.assertIsNone(res.json()["proposal"])

    def test_stage_shift_requires_confirmation_and_cannot_replay(self):
        with patch("assistant_service.zen_access", return_value=("test-key", "https://example.invalid")), patch(
            "assistant_service._ask_zen",
            return_value={"answer": "Подготовлен перенос.", "evidence": [],
                          "action": {"kind": "shift_stage", "stage_id": self.stage_id, "days": 7}},
        ):
            res = self.client.post("/api/assistant/query", json={"message": "Сдвинь котлован на неделю", "object_id": self.object_id})
        self.assertEqual(res.status_code, 200, res.text)
        proposal = res.json()["proposal"]
        self.assertEqual(proposal["new_from"], "2026-09-08")
        self.assertEqual(db.query("SELECT date_from FROM stages WHERE id=?", (self.stage_id,))[0]["date_from"], "2026-09-01")
        confirmed = self.client.post(f"/api/assistant/proposals/{proposal['id']}/confirm")
        self.assertEqual(confirmed.status_code, 200, confirmed.text)
        self.assertEqual(db.query("SELECT date_from FROM stages WHERE id=?", (self.stage_id,))[0]["date_from"], "2026-09-08")
        self.assertEqual(self.client.post(f"/api/assistant/proposals/{proposal['id']}/confirm").status_code, 409)

    def test_missing_key_and_invalid_scope(self):
        with patch("assistant_service.zen_access", return_value=None):
            res = self.client.post("/api/assistant/query", json={"message": "Статус?"})
        self.assertEqual(res.status_code, 503)
        self.assertEqual(self.client.post("/api/assistant/query", json={"message": "Статус?", "object_id": -1}).status_code, 422)

    def test_regular_zen_key_precedes_go_key(self):
        home = Path(self.temp.name)
        auth = home / ".pi/agent/auth.json"
        auth.parent.mkdir(parents=True)
        auth.write_text(json.dumps({
            "opencode": {"type": "api", "key": "zen-test"},
            "opencode-go": {"type": "api", "key": "go-test"},
        }))
        env = {key: value for key, value in environ.items()
               if key not in {"BUILDWATCH_ZEN_KEY", "OPENCODE_API_KEY"}}
        with patch.dict(environ, env, clear=True), patch("assistant_service.Path.home", return_value=home):
            self.assertEqual(assistant_service.zen_access(), ("zen-test", assistant_service.ZEN_URL))

    def test_rejected_zen_credential_falls_back_to_go(self):
        answer = {"answer": "План найден.", "evidence": [f"object:{self.object_id}"], "action": None}
        with patch("assistant_service.zen_access", return_value=("zen-test", assistant_service.ZEN_URL)), patch(
            "assistant_service._saved_key", return_value="go-test",
        ), patch("assistant_service._ask_zen", side_effect=[assistant_service.ZenAuthError(), answer]) as ask:
            res = self.client.post("/api/assistant/query", json={"message": "Какой план?", "object_id": self.object_id})
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(ask.call_count, 2)
        self.assertEqual(ask.call_args.args[3], assistant_service.GO_URL)

    def test_zen_request_body_uses_allowed_reasoning_effort(self):
        body = assistant_service._zen_request_body("Какой этап?", {"scope": "portfolio", "objects": []})
        self.assertIn(body["reasoning_effort"], assistant_service.REASONING_EFFORTS)
        self.assertNotEqual(body["reasoning_effort"], "minimal")
        self.assertTrue(body["model"])
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertEqual(body["messages"][1]["role"], "user")

    def test_invalid_reasoning_effort_env_falls_back_to_low(self):
        with patch.dict(environ, {"BUILDWATCH_ZEN_REASONING_EFFORT": "minimal"}, clear=False):
            self.assertEqual(assistant_service._zen_reasoning_effort(), "low")


if __name__ == "__main__":
    unittest.main()
