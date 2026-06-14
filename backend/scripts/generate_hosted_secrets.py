from __future__ import annotations

import base64
import secrets


def token_urlsafe(length: int = 48) -> str:
    return secrets.token_urlsafe(length)


def totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def main() -> None:
    values = {
        "CELTM_JWT_SECRET": token_urlsafe(64),
        "ADMIN_PASS": token_urlsafe(32),
        "ADMIN_GATEWAY_CODE": token_urlsafe(24),
        "MONITORING_TOKEN": token_urlsafe(32),
        "ADMIN_MFA_SECRET": totp_secret(),
    }
    for key, value in values.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    main()
