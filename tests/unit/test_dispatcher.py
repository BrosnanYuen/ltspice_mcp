from pathlib import Path

import pytest

from ltspice_mcp.config import ServerConfig
from ltspice_mcp.dispatcher import ApiDispatcher


class DummyObject:
    def __init__(self):
        self.value = 0

    def set_tolerance(self, ref: str, new_tolerance: float, distribution: str = "uniform"):
        self.value = new_tolerance
        return {"ref": ref, "distribution": distribution, "value": self.value}


def _config(tmp_path: Path) -> ServerConfig:
    return ServerConfig(
        mcp_server_name="x",
        mcp_server_url="stdio://",
        wine_path=str(tmp_path / "wine"),
        ltspice_path=str(tmp_path / "ltspice.exe"),
        enable_extra_tools=True,
        timeout=10,
    )


def test_execute_known_function(tmp_path: Path):
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)
    out_name, out = d.execute_api("all_loggers", {})
    assert out_name is None
    assert isinstance(out["result"], list)
    assert "spicelib.SimRunner" in out["result"]


def test_execute_stores_object_with_new_name(tmp_path: Path):
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)
    out_name, out = d.execute_api("RawWrite", {"new_object_name": "raw_writer"})
    assert out_name == "raw_writer"
    assert "raw_writer" in d.registry
    assert out["result"]["type"].endswith("RawWrite")


def test_execute_object_method_without_dotted_name(tmp_path: Path):
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)
    d.registry["mc"] = DummyObject()
    out_name, out = d.execute_api(
        "set_tolerance",
        {
            "object_name": "mc",
            "ref": "C",
            "new_tolerance": 0.1,
            "distribution": "uniform",
        },
    )
    assert out_name is None
    assert out["result"]["value"] == 0.1


def test_execute_unknown_api_raises(tmp_path: Path):
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)
    with pytest.raises(ValueError):
        d.execute_api("does_not_exist", {})
