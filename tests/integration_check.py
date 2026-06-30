from __future__ import annotations

import os
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from bmi_logic import bmi_category
from server import (
    create_session_token,
    create_user,
    delete_session,
    get_user_by_email,
    get_user_by_session,
    init_db,
    response_payload,
    update_user,
    validate_profile,
    verify_password,
)


def main():
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required for integration_check.py")

    init_db()

    unique = uuid.uuid4().hex[:10]
    email = f"bmi-{unique}@example.com"
    payload = {
        "firstName": "Victor",
        "lastName": "Tester",
        "email": email,
        "password": "secret123",
        "age": 34,
        "gender": "Male",
        "heightCm": 180,
        "weightKg": 81,
    }

    validated = validate_profile(payload, require_password=True)
    assert validated["errors"] == {}, validated["errors"]
    created = create_user(validated["clean"])
    assert created["email"] == email, created
    assert verify_password("secret123", created["password_hash"])

    fetched = get_user_by_email(email)
    assert fetched and fetched["id"] == created["id"], fetched

    result = response_payload(fetched)
    assert result["bmi"]["category"] == "Healthy", result

    updated = update_user(
        fetched["id"],
        {
            "first_name": "Victor",
            "last_name": "Tester",
            "age": 34,
            "gender": "Male",
            "height_cm": 180,
            "weight_kg": 95,
        },
    )
    updated_result = response_payload(updated)
    assert bmi_category(updated_result["bmi"]["value"]) == "Overweight", updated_result

    token, _ = create_session_token(updated["id"])
    session_user = get_user_by_session(token)
    assert session_user and session_user["id"] == updated["id"], session_user
    delete_session(token)
    assert get_user_by_session(token) is None


if __name__ == "__main__":
    main()
