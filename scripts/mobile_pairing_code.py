from src.modules.mobile_api.auth import pairing_code
from src.shared.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    secret = (settings.mobile_auth_secret or "").strip()
    if len(secret) < 32:
        raise SystemExit("AI_CORP_MOBILE_AUTH_SECRET is not configured")
    print(
        pairing_code(
            secret,
            window_seconds=settings.mobile_pairing_window_seconds,
        )
    )


if __name__ == "__main__":
    main()
