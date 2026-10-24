import pytest

from app.config import ConfigError, load_settings
from tests.conftest import TEST_MASTER_KEY

VALID = {
    "dev": False,
    "database_url": "sqlite:///x.db",
    "master_key": TEST_MASTER_KEY,
    "setup_token": "s" * 32,
    "cf_access_team_domain": "team.cloudflareaccess.com",
    "cf_access_aud": "aud",
}


def test_valid_production_settings():
    settings = load_settings(**VALID)
    assert len(settings.master_key_bytes) == 32
    assert settings.admin_host == "famapp-admin.cowflex.com" and settings.app_host == "famapp.cowflex.com"


def test_dev_mode_fills_defaults():
    settings = load_settings(dev=True, database_url=None, master_key=None, setup_token=None)
    assert settings.database_url == "sqlite:///./dev.db"
    assert len(settings.master_key_bytes) == 32
    assert settings.cf_access_aud is None


@pytest.mark.parametrize(
    "missing", ["database_url", "master_key", "setup_token", "cf_access_team_domain", "cf_access_aud"]
)
def test_missing_value_fails_fast_and_names_it(missing, monkeypatch):
    for name in ("DATABASE_URL", "MASTER_KEY", "SETUP_TOKEN", "CF_ACCESS_TEAM_DOMAIN", "CF_ACCESS_AUD"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigError, match=missing.upper()):
        load_settings(**{**VALID, missing: None})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("master_key", "c2hvcnQ=", "MASTER_KEY must be base64 of exactly 32 bytes"),
        ("master_key", "not base64!!", "MASTER_KEY must be base64"),
        ("setup_token", "short", "SETUP_TOKEN must be at least 32"),
        ("cf_access_team_domain", "https://team.cloudflareaccess.com", "bare host name"),
    ],
)
def test_malformed_values(field, value, message):
    with pytest.raises(ConfigError, match=message) as info:
        load_settings(**{**VALID, field: value})
    assert value not in str(info.value)  # never echo values


def test_type_errors_do_not_leak_values():
    with pytest.raises(ConfigError) as info:
        load_settings(**{**VALID, "admin_dev_port": "secret-looking-value"})
    assert "secret-looking-value" not in str(info.value)
