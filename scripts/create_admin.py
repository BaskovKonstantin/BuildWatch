import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import db
from security import hash_password
email=sys.argv[1] if len(sys.argv)>1 else "admin@buildwatch.local"
password=sys.argv[2] if len(sys.argv)>2 else None
if not password: raise SystemExit("usage: create_admin.py EMAIL PASSWORD")
db.init()
db.execute("INSERT INTO users(email,password_hash,role) VALUES (?,?,?) ON CONFLICT(email) DO UPDATE SET password_hash=excluded.password_hash, role='admin'",(email.lower(),hash_password(password)))
print(f"admin ready: {email}")
