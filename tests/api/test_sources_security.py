import pytest


def test_validate_source_url_blocks_localhost(monkeypatch):
    monkeypatch.delenv("OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS", raising=False)
    from api.routers.sources import validate_source_url

    with pytest.raises(ValueError, match="not allowed"):
        validate_source_url("http://localhost:8000/private")


def test_validate_source_url_blocks_private_ip(monkeypatch):
    monkeypatch.delenv("OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS", raising=False)
    from api.routers.sources import validate_source_url

    with pytest.raises(ValueError, match="not allowed"):
        validate_source_url("http://192.168.1.20/resource")


def test_validate_source_url_allows_public_https(monkeypatch):
    monkeypatch.delenv("OPEN_NOTEBOOK_ALLOW_PRIVATE_SOURCE_URLS", raising=False)
    from api.routers.sources import validate_source_url

    validate_source_url("https://example.org/public-document")
