from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import traceback
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
from psycopg2.extras import RealDictCursor

from bmi_logic import bmi_category, bmi_value


APP_ROOT = Path(__file__).parent
STATIC_ROOT = APP_ROOT / "public"
DATABASE_URL = os.environ.get("DATABASE_URL", "")
PORT = int(os.environ.get("PORT", "8000"))
SESSION_DAYS = 30


def normalize_base_path(value: str | None) -> str:
    if not value or value == "/":
        return ""
    return "/" + value.strip("/")


BASE_PATH = normalize_base_path(
    os.environ.get("X_FORWARDED_PREFIX") or os.environ.get("BASE_PATH")
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, salt: str | None = None) -> str:
    actual_salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), actual_salt.encode("utf-8"), 200_000
    ).hex()
    return f"{actual_salt}${derived}"


def verify_password(password: str, stored: str) -> bool:
    salt, expected = stored.split("$", 1)
    derived = hash_password(password, salt).split("$", 1)[1]
    return hmac.compare_digest(derived, expected)


def open_db():
    return psycopg2.connect(DATABASE_URL)


def init_db() -> None:
    with open_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists users (
                    id bigserial primary key,
                    email text not null unique,
                    password_hash text not null,
                    first_name text not null,
                    last_name text not null,
                    age integer not null,
                    gender text not null,
                    height_cm numeric(6,2) not null,
                    weight_kg numeric(6,2) not null,
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                );

                create table if not exists sessions (
                    token text primary key,
                    user_id bigint not null references users(id) on delete cascade,
                    created_at timestamptz not null default now(),
                    expires_at timestamptz not null
                );
                """
            )
        conn.commit()


def parse_json(handler: "AppHandler") -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def response_payload(user: dict) -> dict:
    height_cm = float(user["height_cm"])
    weight_kg = float(user["weight_kg"])
    bmi = bmi_value(height_cm, weight_kg)
    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "firstName": user["first_name"],
            "lastName": user["last_name"],
            "age": user["age"],
            "gender": user["gender"],
            "heightCm": height_cm,
            "weightKg": weight_kg,
        },
        "bmi": {"value": bmi, "category": bmi_category(bmi)},
    }


def get_user_by_email(email: str) -> dict | None:
    with open_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("select * from users where email = %s", (email,))
            return cur.fetchone()


def create_user(clean: dict) -> dict:
    with open_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                insert into users
                    (email, password_hash, first_name, last_name, age, gender, height_cm, weight_kg)
                values
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                returning *
                """,
                (
                    clean["email"],
                    hash_password(clean["password"]),
                    clean["first_name"],
                    clean["last_name"],
                    clean["age"],
                    clean["gender"],
                    clean["height_cm"],
                    clean["weight_kg"],
                ),
            )
            user = cur.fetchone()
        conn.commit()
    return user


def update_user(user_id: int, clean: dict) -> dict:
    with open_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                update users
                set first_name = %s,
                    last_name = %s,
                    age = %s,
                    gender = %s,
                    height_cm = %s,
                    weight_kg = %s,
                    updated_at = now()
                where id = %s
                returning *
                """,
                (
                    clean["first_name"],
                    clean["last_name"],
                    clean["age"],
                    clean["gender"],
                    clean["height_cm"],
                    clean["weight_kg"],
                    user_id,
                ),
            )
            user = cur.fetchone()
        conn.commit()
    return user


def create_session_token(user_id: int) -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = now_utc() + timedelta(days=SESSION_DAYS)
    with open_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into sessions (token, user_id, expires_at) values (%s, %s, %s)",
                (token, user_id, expires_at),
            )
        conn.commit()
    return token, expires_at


def get_user_by_session(token: str) -> dict | None:
    with open_db() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                select u.*
                from sessions s
                join users u on u.id = s.user_id
                where s.token = %s and s.expires_at > now()
                """,
                (token,),
            )
            return cur.fetchone()


def delete_session(token: str) -> None:
    with open_db() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from sessions where token = %s", (token,))
        conn.commit()


def validate_profile(data: dict, *, require_password: bool) -> dict:
    errors: dict[str, str] = {}
    first_name = str(data.get("firstName", "")).strip()
    last_name = str(data.get("lastName", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    gender = str(data.get("gender", "")).strip()

    if len(first_name) < 2:
        errors["firstName"] = "First name must be at least 2 characters."
    if len(last_name) < 2:
        errors["lastName"] = "Last name must be at least 2 characters."
    if "@" not in email or "." not in email.split("@")[-1]:
        errors["email"] = "Enter a valid email address."
    if require_password and len(password) < 8:
        errors["password"] = "Password must be at least 8 characters."
    if gender not in {"Male", "Female", "Other"}:
        errors["gender"] = "Choose a gender option."

    try:
        age = int(data.get("age"))
        if age < 13 or age > 120:
            raise ValueError
    except Exception:
        errors["age"] = "Age must be between 13 and 120."
        age = 0

    try:
        height_cm = float(data.get("heightCm"))
        if height_cm < 80 or height_cm > 260:
            raise ValueError
    except Exception:
        errors["heightCm"] = "Height must be between 80 cm and 260 cm."
        height_cm = 0

    try:
        weight_kg = float(data.get("weightKg"))
        if weight_kg < 20 or weight_kg > 500:
            raise ValueError
    except Exception:
        errors["weightKg"] = "Weight must be between 20 kg and 500 kg."
        weight_kg = 0

    return {
        "errors": errors,
        "clean": {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password": password,
            "age": age,
            "gender": gender,
            "height_cm": height_cm,
            "weight_kg": weight_kg,
        },
    }


class AppHandler(BaseHTTPRequestHandler):
    server_version = "BmiCalculator/1.0"

    def do_GET(self) -> None:
        try:
            path = self.route_path()
            if path == "/api/health":
                self.send_json({"status": "ok", "basePath": BASE_PATH})
                return
            if path == "/api/me":
                user = self.require_user()
                if not user:
                    return
                self.send_json(response_payload(user))
                return
            self.serve_asset(path)
        except Exception as exc:
            self.handle_error(exc)

    def do_POST(self) -> None:
        try:
            path = self.route_path()
            if path == "/api/register":
                self.register()
                return
            if path == "/api/login":
                self.login()
                return
            if path == "/api/logout":
                self.logout()
                return
            self.send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.handle_error(exc)

    def do_PUT(self) -> None:
        try:
            path = self.route_path()
            if path == "/api/profile":
                self.update_profile()
                return
            self.send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.handle_error(exc)

    def log_message(self, format: str, *args) -> None:
        return

    def route_path(self) -> str:
        raw_path = urlparse(self.path).path
        if BASE_PATH and raw_path.startswith(BASE_PATH):
            stripped = raw_path[len(BASE_PATH) :]
            return stripped or "/"
        return raw_path or "/"

    def send_json(self, data: dict, status: HTTPStatus = HTTPStatus.OK, cookie: str | None = None) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def redirect_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_error(self, exc: Exception) -> None:
        traceback.print_exc()
        self.send_json(
            {"error": "Internal server error.", "detail": str(exc)},
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    def serve_asset(self, route_path: str) -> None:
        if route_path in {"/", ""}:
            html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
            base_href = f"{BASE_PATH}/" if BASE_PATH else "/"
            page = html.replace("__BASE_HREF__", base_href).replace(
                "__API_BASE__", BASE_PATH or ""
            )
            self.redirect_html(page)
            return

        asset_path = (STATIC_ROOT / route_path.lstrip("/")).resolve()
        if STATIC_ROOT not in asset_path.parents and asset_path != STATIC_ROOT:
            self.send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return
        if not asset_path.exists() or not asset_path.is_file():
            self.send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
            return

        mime = {
            ".js": "application/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".json": "application/json; charset=utf-8",
        }.get(asset_path.suffix, "application/octet-stream")
        body = asset_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def parse_cookies(self) -> SimpleCookie:
        cookies = SimpleCookie()
        cookies.load(self.headers.get("Cookie", ""))
        return cookies

    def session_cookie(self, token: str, expires_at: datetime | None = None) -> str:
        parts = [f"session_token={token if expires_at else ''}", "Path=/", "HttpOnly", "SameSite=Lax"]
        if expires_at:
            parts.append(f"Expires={expires_at.strftime('%a, %d %b %Y %H:%M:%S GMT')}")
        else:
            parts.append("Expires=Thu, 01 Jan 1970 00:00:00 GMT")
        return "; ".join(parts)

    def current_user(self) -> dict | None:
        cookies = self.parse_cookies()
        token = cookies.get("session_token")
        if not token:
            return None
        return get_user_by_session(token.value)

    def require_user(self) -> dict | None:
        user = self.current_user()
        if not user:
            self.send_json({"error": "Authentication required."}, status=HTTPStatus.UNAUTHORIZED)
            return None
        return user

    def create_session(self, user_id: int) -> str:
        token, expires_at = create_session_token(user_id)
        return self.session_cookie(token, expires_at)

    def register(self) -> None:
        payload = parse_json(self)
        validated = validate_profile(payload, require_password=True)
        if validated["errors"]:
            self.send_json(
                {"error": "Validation failed.", "fieldErrors": validated["errors"]},
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        clean = validated["clean"]

        if get_user_by_email(clean["email"]):
            self.send_json(
                {"error": "An account with that email already exists."},
                status=HTTPStatus.CONFLICT,
            )
            return
        user = create_user(clean)

        cookie = self.create_session(user["id"])
        self.send_json(
            {"message": "Account created.", **response_payload(user)},
            status=HTTPStatus.CREATED,
            cookie=cookie,
        )

    def login(self) -> None:
        payload = parse_json(self)
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        if not email or not password:
            self.send_json(
                {"error": "Email and password are required."},
                status=HTTPStatus.BAD_REQUEST,
            )
            return

        user = get_user_by_email(email)

        if not user or not verify_password(password, user["password_hash"]):
            self.send_json(
                {"error": "Invalid email or password."},
                status=HTTPStatus.UNAUTHORIZED,
            )
            return

        cookie = self.create_session(user["id"])
        self.send_json({"message": "Logged in.", **response_payload(user)}, cookie=cookie)

    def logout(self) -> None:
        cookies = self.parse_cookies()
        token = cookies.get("session_token")
        if token:
            delete_session(token.value)
        self.send_json({"message": "Logged out."}, cookie=self.session_cookie("", None))

    def update_profile(self) -> None:
        user = self.require_user()
        if not user:
            return

        payload = parse_json(self)
        validated = validate_profile({**payload, "email": user["email"]}, require_password=False)
        if validated["errors"]:
            validated["errors"].pop("email", None)
            if validated["errors"]:
                self.send_json(
                    {"error": "Validation failed.", "fieldErrors": validated["errors"]},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
        clean = validated["clean"]

        updated = update_user(user["id"], clean)
        self.send_json({"message": "Profile updated.", **response_payload(updated)})


def run() -> None:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is required.")
    init_db()
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), AppHandler)
    print(f"Listening on http://127.0.0.1:{PORT}{BASE_PATH or '/'}")
    httpd.serve_forever()


if __name__ == "__main__":
    run()
