from src.modules.mobile_api.auth import pairing_code, resolve_mobile_auth_secret
from src.shared.config.settings import get_settings


def main() -> None:
    settings = get_settings()
    secret = resolve_mobile_auth_secret(settings)
    if secret is None:
        raise SystemExit(
            "Mobile auth is not configured: set AI_CORP_MOBILE_AUTH_SECRET "
            "or enable safe pilot auth credentials."
        )
    print(
        pairing_code(
            secret,
            window_seconds=settings.mobile_pairing_window_seconds,
        )
    )


if __name__ == "__main__":
    main()
