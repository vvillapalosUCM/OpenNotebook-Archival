import importlib
import pytest


@pytest.mark.asyncio
async def test_update_check_disabled_by_default(monkeypatch):
    monkeypatch.setenv("OPEN_NOTEBOOK_ENABLE_UPDATE_CHECK", "false")
    import api.routers.config as config_module
    config_module = importlib.reload(config_module)

    latest, has_update = await config_module.get_latest_version_cached("1.0.0")
    assert latest is None
    assert has_update is False
    assert config_module.ENABLE_UPDATE_CHECK is False


@pytest.mark.asyncio
async def test_config_endpoint_reports_update_check_flag(monkeypatch):
    monkeypatch.setenv("OPEN_NOTEBOOK_ENABLE_UPDATE_CHECK", "false")
    import api.routers.config as config_module
    config_module = importlib.reload(config_module)

    async def fake_db_health():
        return {"status": "online"}

    monkeypatch.setattr(config_module, "check_database_health", fake_db_health)

    result = await config_module.get_config(request=None)
    assert result["updateCheckEnabled"] is False
    assert result["dbStatus"] == "online"
