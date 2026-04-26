from pathlib import Path

import pytest

from ltspice_mcp.config import ServerConfig


def test_config_supports_required_schemes(tmp_path: Path):
    cfg = ServerConfig(
        mcp_server_name="x",
        mcp_server_url="stdio://",
        wine_path=str(tmp_path / "wine"),
        ltspice_path=str(tmp_path / "ltspice.exe"),
        enable_extra_tools=True,
        timeout=10,
    )
    assert cfg.mcp_server_url == "stdio://"


@pytest.mark.parametrize("url", ["http://localhost:7543", "https://localhost:7543", "stdio://"])
def test_config_url_variants(url: str, tmp_path: Path):
    cfg = ServerConfig(
        mcp_server_name="x",
        mcp_server_url=url,
        wine_path=str(tmp_path / "wine"),
        ltspice_path=str(tmp_path / "ltspice.exe"),
        enable_extra_tools=True,
        timeout=10,
    )
    assert cfg.mcp_server_url == url


def test_invalid_scheme_rejected(tmp_path: Path):
    with pytest.raises(ValueError):
        ServerConfig(
            mcp_server_name="x",
            mcp_server_url="ftp://localhost:7543",
            wine_path=str(tmp_path / "wine"),
            ltspice_path=str(tmp_path / "ltspice.exe"),
            enable_extra_tools=True,
            timeout=10,
        )


def test_ltspice_path_dedupes_repeated_exe_suffix():
    cfg = ServerConfig(
        mcp_server_name="x",
        mcp_server_url="stdio://",
        wine_path="/usr/bin/wine",
        ltspice_path="/tmp/LTspice.exeLTspice.exe",
        enable_extra_tools=True,
        timeout=10,
    )
    assert cfg.ltspice_path.endswith("/tmp/LTspice.exe")
