"""Unit tests for corporate CA / Zscaler SSL bootstrap (no live network)."""

from pathlib import Path

import pytest

import app.ssl_bootstrap as ssl_bootstrap


@pytest.fixture(autouse=True)
def _reset_ssl_state():
    ssl_bootstrap.reset_ssl_bootstrap_for_tests()
    yield
    ssl_bootstrap.reset_ssl_bootstrap_for_tests()


def test_resolve_ca_bundle_prefers_ssl_cert_file(monkeypatch, tmp_path: Path):
    bundle = tmp_path / "corp-ca.pem"
    bundle.write_text("placeholder")
    monkeypatch.setenv("SSL_CERT_FILE", str(bundle))
    monkeypatch.setattr(ssl_bootstrap, "DEFAULT_CORP_BUNDLES", ())
    assert ssl_bootstrap.resolve_ca_bundle() == bundle


def test_resolve_ca_bundle_none_when_missing(monkeypatch):
    for key in (
        "SSL_CERT_FILE",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "AWS_CA_BUNDLE",
        "HTTPLIB2_CA_CERTS",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(ssl_bootstrap, "DEFAULT_CORP_BUNDLES", ())
    assert ssl_bootstrap.resolve_ca_bundle() is None


def test_configure_ssl_sets_env_and_active_bundle(monkeypatch, tmp_path: Path):
    bundle = tmp_path / "corp-ca.pem"
    # Path is used as httpx verify=; content is not parsed at configure time.
    bundle.write_text("placeholder-ca\n")
    monkeypatch.setenv("SSL_CERT_FILE", str(bundle))
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.setattr(ssl_bootstrap, "DEFAULT_CORP_BUNDLES", ())
    path = ssl_bootstrap.configure_ssl(force=True)
    assert path == bundle
    assert ssl_bootstrap._active_bundle == str(bundle)
    import os

    assert os.environ.get("REQUESTS_CA_BUNDLE") == str(bundle)
