from __future__ import annotations
import json
import db

def record(action: str, entity: str | None = None, entity_id: int | None = None, user_id: int | None = None, details: dict | None = None) -> None:
    db.execute("INSERT INTO audit_log(user_id,action,entity,entity_id,details) VALUES (?,?,?,?,?)", (user_id, action, entity, entity_id, json.dumps(details or {}, ensure_ascii=False)))
