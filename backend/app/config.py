"""Configuration from environment variables (spec-backend-skeleton.md, decisions section 3).

Outside dev mode every required value must be present and well-formed; otherwise the process
stops at start with an error that names the variable, never its value.
"""

from __future__ import annotations

import base64
import binascii
from functools import lru_cache

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.db.session import DEFAULT_DATABASE_URL

# Dev-only placeholders; FAMAPP_DEV=1 is never set in deploy files.
DEV_MASTER_KEY = base64.b64encode(b"famapp-dev-master-key-not-secret").decode()
DEV_SETUP_TOKEN = "famapp-dev-setup-token-not-a-secret"


class ConfigError(Exception):
    pass


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True)

    dev: bool = Field(False, alias="FAMAPP_DEV")
    database_url: str | None = Field(None, alias="DATABASE_URL")
    master_key: SecretStr | None = Field(None, alias="MASTER_KEY")
    setup_token: SecretStr | None = Field(None, alias="SETUP_TOKEN")
    cf_access_team_domain: str | None = Field(None, alias="CF_ACCESS_TEAM_DOMAIN")
    cf_access_aud: str | None = Field(None, alias="CF_ACCESS_AUD")
    app_host: str = Field("famapp.cowflex.com", alias="APP_HOST")
    admin_host: str = Field("famapp-admin.cowflex.com", alias="ADMIN_HOST")
    admin_dev_port: int = Field(5000, alias="ADMIN_DEV_PORT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    def resolved(self) -> Settings:
        """Apply dev defaults, then check required values. Raises ConfigError."""
        values = {}
        if self.dev:
            values = {
                "database_url": self.database_url or DEFAULT_DATABASE_URL,
                "master_key": self.master_key or SecretStr(DEV_MASTER_KEY),
                "setup_token": self.setup_token or SecretStr(DEV_SETUP_TOKEN),
            }
        settings = self.model_copy(update=values)
        settings._check()
        return settings

    def _check(self) -> None:
        problems = []
        required = {"DATABASE_URL": self.database_url, "MASTER_KEY": self.master_key, "SETUP_TOKEN": self.setup_token}
        if not self.dev:
            required |= {"CF_ACCESS_TEAM_DOMAIN": self.cf_access_team_domain, "CF_ACCESS_AUD": self.cf_access_aud}
        problems += [f"{name} is not set" for name, value in required.items() if not value]
        if self.master_key and not _is_32_byte_key(self.master_key.get_secret_value()):
            problems.append("MASTER_KEY must be base64 of exactly 32 bytes (openssl rand -base64 32)")
        if self.setup_token and len(self.setup_token.get_secret_value()) < 32:
            problems.append("SETUP_TOKEN must be at least 32 characters (openssl rand -hex 32)")
        domain = self.cf_access_team_domain
        if domain and ("://" in domain or "/" in domain):
            problems.append("CF_ACCESS_TEAM_DOMAIN must be a bare host name like <team>.cloudflareaccess.com")
        if problems:
            raise ConfigError("; ".join(problems))

    @property
    def master_key_bytes(self) -> bytes:
        assert self.master_key is not None
        return base64.b64decode(self.master_key.get_secret_value(), validate=True)


def _is_32_byte_key(value: str) -> bool:
    try:
        return len(base64.b64decode(value, validate=True)) == 32
    except (binascii.Error, ValueError):
        return False


def load_settings(**overrides) -> Settings:
    """Settings from the environment (overrides: field values, for tests)."""
    try:
        settings = Settings(**overrides)
    except ValidationError as exc:
        names = ", ".join(".".join(str(p) for p in error["loc"]) for error in exc.errors())
        raise ConfigError(f"invalid configuration: {names}") from None
    return settings.resolved()


@lru_cache
def get_settings() -> Settings:
    return load_settings()
