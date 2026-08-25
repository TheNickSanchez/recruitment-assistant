"""Point TLS verification at a corporate CA bundle (e.g. Zscaler).

CrewAI PlusAPI builds ``httpx.Client(trust_env=False, verify=True)``, which
ignores ``SSL_CERT_FILE`` / ``REQUESTS_CA_BUNDLE``. Without an explicit
``verify=<bundle path>``, AMP trace uploads fail with
``CERTIFICATE_VERIFY_FAILED`` behind SSL intercept.
"""

from __future__ import annotations

import os
from pathlib import Path

from app.logging_config import get_logger

logger = get_logger("ssl")

# Known corp installs (used only when present on disk; never required).
DEFAULT_CORP_BUNDLES: tuple[str, ...] = (
    "/Library/Application Support/DocuSign/zscaler-ca-bundle.pem",
)

_active_bundle: str | None = None
_httpx_patched = False
_configured = False

def _first_existing(*candidates: str | None) -> Path | None:
    for raw in candidates:
        if not raw or not str(raw).strip():
            continue
        path = Path(str(raw).strip())
        if path.is_file():
            return path
    return None


def resolve_ca_bundle() -> Path | None:
    """Prefer explicit env vars, then known corp bundle paths if present."""
    return _first_existing(
        os.getenv("SSL_CERT_FILE"),
        os.getenv("REQUESTS_CA_BUNDLE"),
        os.getenv("CURL_CA_BUNDLE"),
        os.getenv("AWS_CA_BUNDLE"),
        os.getenv("HTTPLIB2_CA_CERTS"),
        *DEFAULT_CORP_BUNDLES,
    )


def configure_ssl(*, force: bool = False) -> Path | None:
    """Idempotent. Returns the bundle path if configured, else None."""
    global _active_bundle, _configured
    if _configured and not force:
        return Path(_active_bundle) if _active_bundle else None

    bundle = resolve_ca_bundle()
    if bundle is None:
        _active_bundle = None
        _configured = True
        return None

    # Use the PEM path (not ssl.create_default_context): OpenSSL 3 rejects some
    # corp roots with "Basic Constraints of CA cert not marked critical".
    bundle_str = str(bundle)
    _active_bundle = bundle_str
    for key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        os.environ.setdefault(key, bundle_str)

    _patch_httpx_clients()
    _configured = True
    logger.info("tls ca bundle configured path=%s", bundle_str)
    return bundle


def _patch_httpx_clients() -> None:
    """Force corp CA when verify is the boolean True default."""
    global _httpx_patched
    if _httpx_patched:
        return

    import httpx

    for cls in (httpx.Client, httpx.AsyncClient):
        original_init = cls.__init__

        def _init(self, *args, _orig=original_init, **kwargs):  # type: ignore[no-untyped-def]
            verify = kwargs.get("verify", True)
            if verify is True and _active_bundle:
                kwargs["verify"] = _active_bundle
            return _orig(self, *args, **kwargs)

        cls.__init__ = _init  # type: ignore[method-assign]

    _httpx_patched = True


def reset_ssl_bootstrap_for_tests() -> None:
    """Test helper: clear module state (does not unpatch httpx)."""
    global _active_bundle, _configured
    _active_bundle = None
    _configured = False