"""Generate a JWT test token for integration testing."""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from jose import jwt
from app.config import settings

user_id = str(uuid4())
token = jwt.encode(
    {
        "sub": user_id,
        "role": "admin",
        "exp": datetime.now(timezone.utc) + timedelta(days=30),
    },
    settings.secret_key,
    algorithm="HS256",
)

print(f"User ID: {user_id}")
print(f"Token: {token}")
