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


class DummyTrace:
    def __init__(self, waves):
        self._waves = waves

    def get_wave(self, wave: int):
        return self._waves[wave]


class DummyRaw:
    def __init__(self):
        self._steps = [0, 1]
        self._axis = [[0.0, 1.0, 2.0], [0.0, 1.0]]
        self._traces = {
            "V(opamp_input)": DummyTrace([[10.0, 11.0, 12.0], [20.0, 21.0]]),
            "V(opamp_output)": DummyTrace([[100.0, 101.0, 102.0], [200.0, 201.0]]),
        }

    def get_steps(self):
        return self._steps

    def get_axis(self, wave: int):
        return self._axis[wave]

    def get_trace(self, trace_ref: str):
        return self._traces[trace_ref]


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


def test_traces_to_csv_writes_all_waves(tmp_path: Path):
    d = ApiDispatcher(config=_config(tmp_path), project_root=tmp_path)
    d.registry["raw"] = DummyRaw()

    out_name, out = d.execute_api(
        "traces_to_csv",
        {
            "object_name": "raw",
            "trace_refs": ["V(opamp_input)", "V(opamp_output)"],
            "output_files": "./sim_wave_",
        },
    )
    assert out_name is None
    result = out["result"]
    assert result["wave_count"] == 2
    assert len(result["written_files"]) == 2

    csv0 = Path(result["written_files"][0]).read_text(encoding="utf-8")
    csv1 = Path(result["written_files"][1]).read_text(encoding="utf-8")

    assert "xaxis,V(opamp_input),V(opamp_output)" in csv0
    assert "0.0,10.0,100.0" in csv0
    assert "2.0,12.0,102.0" in csv0
    assert "xaxis,V(opamp_input),V(opamp_output)" in csv1
    assert "1.0,21.0,201.0" in csv1
