from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ServerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mcp_server_name: str = Field(default="My PyLTSpice MCP Server")
    mcp_server_url: str = Field(default="stdio://")
    wine_path: str | None = Field(default=None)
    ltspice_path: str = Field(default="")
    enable_extra_tools: bool = Field(default=True)
    timeout: int = Field(default=600, ge=1)

    @field_validator("mcp_server_url")
    @classmethod
    def validate_server_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https", "stdio"}:
            raise ValueError("mcp_server_url must use http://, https://, or stdio://")
        return value

    @field_validator("ltspice_path", "wine_path")
    @classmethod
    def normalize_paths(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            return value
        return str(Path(value).expanduser().resolve())


DEFAULT_CONFIG = {
    "mcp_server_name": "My PyLTSpice MCP Server",
    "mcp_server_url": "http://localhost:7543",
    "wine_path": "/usr/bin/wine",
    "ltspice_path": "/home/brosnan/.wine/drive_c/Program Files/ADI/LTspice.exe",
    "enable_extra_tools": True,
    "timeout": 600,
}


def load_config(config_path: Path) -> ServerConfig:
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return ServerConfig.model_validate(data)


def write_default_config(config_path: Path) -> None:
    config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n", encoding="utf-8")
