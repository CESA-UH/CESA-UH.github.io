import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.core.config import BACKEND_DIR, settings
from app.core.database import get_db
from app.models.user import User

bearer = HTTPBearer(auto_error=False)


def signing_key():
    if settings.JWT_SECRET_KEY:
        return settings.JWT_SECRET_KEY
    path = BACKEND_DIR / "data" / ".session-key"
    path.parent.mkdir(exist_ok=True)
    try:
        with path.open("x") as f:
            path.chmod(0o600)
            f.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    return path.read_text()


def hash_password(password: str):
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
    return f"pbkdf2_sha256$600000${salt}${digest}"


def verify_password(password: str, encoded: str):
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_for(user: User):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user.id), "iat": now, "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)}, signing_key(), algorithm="HS256")


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)):
    try:
        if credentials is None:
            raise ValueError()
        payload = jwt.decode(credentials.credentials, signing_key(), algorithms=["HS256"], options={"require": ["exp", "sub"]})
        user = db.get(User, int(payload["sub"]))
        if user is None:
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(401, "برای ادامه وارد حساب خود شوید.")
