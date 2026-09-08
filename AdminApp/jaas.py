import os
import time

import jwt
from django.conf import settings


def generate_jaas_jwt(staff, room_name, moderator=False):
    """
    Generate a short-lived JaaS JWT for a CRM staff member.
    """

    private_key_path = os.getenv(
        "JAAS_PRIVATE_KEY_PATH",
        "jaas-private-key.pem"
    )

    # If the path is relative, resolve it from BASE_DIR.
    if not os.path.isabs(private_key_path):
        private_key_path = os.path.join(
            settings.BASE_DIR,
            private_key_path
        )

    if not os.path.exists(private_key_path):
        raise FileNotFoundError(
            f"JaaS private key not found: {private_key_path}"
        )

    with open(private_key_path, "r", encoding="utf-8") as key_file:
        private_key = key_file.read()

    app_id = os.getenv("JAAS_APP_ID")
    key_id = os.getenv("JAAS_KEY_ID")

    if not app_id:
        raise ValueError("JAAS_APP_ID is not configured")

    if not key_id:
        raise ValueError("JAAS_KEY_ID is not configured")

    now = int(time.time())

    payload = {
        "aud": "jitsi",
        "iss": "chat",
        "sub": app_id,

        # Only allow this JWT to access this specific CRM meeting.
        "room": room_name,

        # Token valid for 1 hour.
        "exp": now + 3600,

        # Small clock-skew allowance.
        "nbf": now - 10,

        "context": {
            "user": {
                "id": str(staff.id),
                "name": staff.full_name,
                "email": staff.email,
                "moderator": moderator,
            }
        },
    }

    headers = {
        "alg": "RS256",
        "kid": key_id,
        "typ": "JWT",
    }

    token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers=headers,
    )

    return token