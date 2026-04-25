from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import PyLTSpice
from PyLTSpice import (
    AscEditor,
    LTSpiceLogReader,
    LTspice,
    RawRead,
    RawWrite,
    SimCommander,
    SimRunner,
    SpiceCircuit,
    SpiceEditor,
    SpiceReadException,
    Trace,
    add_log_handler,
    all_loggers,
    set_log_level,
)
from PyLTSpice.log.logfile_data import LTComplex, LogfileData
from PyLTSpice.log.ltsteps import LTSpiceExport, reformat_LTSpice_export
from PyLTSpice.log.semi_dev_op_reader import opLogReader
from PyLTSpice.sim.process_callback import ProcessCallback
from PyLTSpice.sim.sim_stepping import SimStepper
from PyLTSpice.sim.tookit.montecarlo import Montecarlo
from PyLTSpice.sim.tookit.worst_case import WorstCaseAnalysis
from PyLTSpice.utils.detect_encoding import EncodingDetectError, detect_encoding
from PyLTSpice.utils.sweep_iterators import sweep, sweep_iterators, sweep_log, sweep_log_n, sweep_n

from .config import ServerConfig


class UnsupportedFileTypeError(ValueError):
    pass


READ_APIS = {
    "RawRead",
    "LTSpiceRawRead",
    "SpiceCircuit",
    "SpiceEditor",
    "AscEditor",
    "LTSpiceLogReader",
    "LTSpiceExport",
    "opLogReader",
    "detect_encoding",
}


class ApiDispatcher:
    def __init__(self, config: ServerConfig, project_root: Path):
        self.config = config
        self.project_root = project_root.resolve()
        self.registry: dict[str, Any] = {}

    def reset(self) -> None:
        self.registry.clear()

    def execute_api(self, api_name: str, inputs: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        if not isinstance(inputs, dict):
            raise ValueError("inputs must be a JSON object")

        # Dotted API names call methods on object instances.
        if "." in api_name:
            cls_name, method_name = api_name.split(".", 1)
            return self._execute_method(cls_name, method_name, inputs)

        # Allow direct object method calls like set_tolerance.
        if api_name not in self._callables() and "object_name" in inputs:
            target = self._resolve_object_by_name(str(inputs["object_name"]))
            kwargs = self._normalize_kwargs(api_name, {k: v for k, v in inputs.items() if k != "object_name"})
            result = getattr(target, api_name)(**kwargs)
            return None, {"result": self._serialize(result)}

        if api_name not in self._callables():
            raise ValueError(f"unknown api_name: {api_name}")

        kwargs = self._normalize_kwargs(api_name, dict(inputs))

        if api_name in READ_APIS:
            self._validate_read_inputs(api_name, kwargs)

        if api_name == "add_log_handler":
            kwargs = self._normalize_add_handler(kwargs)

        callable_obj = self._callables()[api_name]
        result = callable_obj(**kwargs)

        output_obj_name = None
        new_name = inputs.get("new_object_name")
        if new_name:
            if not isinstance(new_name, str):
                raise ValueError("new_object_name must be a string")
            self.registry[new_name] = result
            output_obj_name = new_name

        return output_obj_name, {"result": self._serialize(result)}

    def _execute_method(self, class_name: str, method_name: str, inputs: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
        target = self._resolve_target_for_method(class_name, inputs)
        kwargs = {k: v for k, v in inputs.items() if k not in {"object_name", "new_object_name"}}
        kwargs = self._normalize_kwargs(f"{class_name}.{method_name}", kwargs)
        result = getattr(target, method_name)(**kwargs)

        output_obj_name = None
        new_name = inputs.get("new_object_name")
        if new_name:
            if not isinstance(new_name, str):
                raise ValueError("new_object_name must be a string")
            self.registry[new_name] = result
            output_obj_name = new_name

        return output_obj_name, {"result": self._serialize(result)}

    def _resolve_target_for_method(self, class_name: str, inputs: dict[str, Any]) -> Any:
        object_name = inputs.get("object_name")
        if object_name:
            return self._resolve_object_by_name(str(object_name))

        matches = [obj for obj in self.registry.values() if obj.__class__.__name__ == class_name]
        if not matches:
            raise ValueError(f"no object found for class {class_name}")
        if len(matches) > 1:
            raise ValueError(f"multiple objects found for class {class_name}; provide object_name")
        return matches[0]

    def _resolve_object_by_name(self, object_name: str) -> Any:
        if object_name not in self.registry:
            raise ValueError(f"unknown object_name: {object_name}")
        return self.registry[object_name]

    def _normalize_kwargs(self, api_name: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in kwargs.items():
            if key == "new_object_name":
                continue
            normalized[key] = self._normalize_value(key, value)

        # Backward-compatible alias.
        if api_name == "LTSpiceRawRead":
            api_name = "RawRead"
        return normalized

    def _normalize_value(self, key: str, value: Any) -> Any:
        if isinstance(value, str):
            # Resolve object references by name when the key implies one.
            if key in {"circuit_file", "circuit", "runner", "editor", "simulator", "spice_tool", "object_name"}:
                if value in self.registry:
                    return self.registry[value]

            # Resolve likely path-like values to absolute host paths.
            if any(token in key.lower() for token in ["file", "path", "folder"]):
                return str((self.project_root / value).resolve()) if not Path(value).is_absolute() else value

        if isinstance(value, list):
            return [self._normalize_value(key, item) for item in value]
        if isinstance(value, dict):
            return {k: self._normalize_value(k, v) for k, v in value.items()}
        return value

    def _normalize_add_handler(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        handler_spec = kwargs.get("handler") or kwargs.get("handler_type")
        if handler_spec is None:
            raise ValueError("add_log_handler requires handler or handler_type")

        if isinstance(handler_spec, str):
            lowered = handler_spec.lower()
            if lowered == "null":
                return {"handler": logging.NullHandler()}
            if lowered == "stream":
                return {"handler": logging.StreamHandler()}
            raise ValueError("unsupported handler_type")

        if isinstance(handler_spec, dict):
            lowered = str(handler_spec.get("type", "")).lower()
            if lowered == "null":
                return {"handler": logging.NullHandler()}
            if lowered == "stream":
                return {"handler": logging.StreamHandler()}
            raise ValueError("unsupported handler.type")

        raise ValueError("handler must be a supported string or object")

    def _validate_read_inputs(self, api_name: str, kwargs: dict[str, Any]) -> None:
        file_arg_keys = [
            "raw_file",
            "raw_filename",
            "netlist_file",
            "circuit_file",
            "asc_file",
            "logfile",
            "log_filename",
            "input_file",
            "export_file",
            "export_filename",
            "file",
            "filename",
        ]
        candidate = None
        for key in file_arg_keys:
            if key in kwargs and isinstance(kwargs[key], str):
                candidate = kwargs[key]
                break

        if candidate is None:
            return

        path = Path(candidate)
        if not path.exists():
            raise FileNotFoundError(str(path))

        ext = path.suffix.lower()
        if api_name in {"AscEditor"} and ext not in {".asc", ".net", ".cir"}:
            raise UnsupportedFileTypeError("AscEditor supports .asc/.net/.cir")
        if api_name in {"SpiceEditor", "SpiceCircuit"} and ext not in {".asc", ".net", ".cir"}:
            raise UnsupportedFileTypeError("Spice editor supports .asc/.net/.cir")
        if api_name in {"RawRead", "LTSpiceRawRead"} and ext != ".raw":
            raise UnsupportedFileTypeError("RawRead supports .raw")
        if api_name in {"LTSpiceLogReader", "opLogReader"} and ext != ".log":
            raise UnsupportedFileTypeError("log reader supports .log")

    def _callables(self) -> dict[str, Any]:
        return {
            "all_loggers": lambda: all_loggers(),
            "set_log_level": lambda level: set_log_level(level),
            "add_log_handler": lambda handler: add_log_handler(handler),
            "RawRead": RawRead,
            "LTSpiceRawRead": RawRead,
            "RawWrite": RawWrite,
            "Trace": Trace,
            "SpiceReadException": SpiceReadException,
            "SpiceCircuit": SpiceCircuit,
            "SpiceEditor": SpiceEditor,
            "AscEditor": AscEditor,
            "SimRunner": SimRunner,
            "SimCommander": SimCommander,
            "LTspice": lambda: LTspice,
            "LTSpiceLogReader": LTSpiceLogReader,
            "reformat_LTSpice_export": reformat_LTSpice_export,
            "LTSpiceExport": LTSpiceExport,
            "LogfileData": LogfileData,
            "LTComplex": LTComplex,
            "opLogReader": opLogReader,
            "ProcessCallback": ProcessCallback,
            "SimStepper": SimStepper,
            "Montecarlo": Montecarlo,
            "WorstCaseAnalysis": WorstCaseAnalysis,
            "sweep": sweep,
            "sweep_n": sweep_n,
            "sweep_log": sweep_log,
            "sweep_log_n": sweep_log_n,
            "sweep_iterators": sweep_iterators,
            "EncodingDetectError": EncodingDetectError,
            "detect_encoding": detect_encoding,
        }

    def _serialize(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Path):
            return str(value.resolve())
        if isinstance(value, dict):
            return {str(k): self._serialize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._serialize(v) for v in value]

        return {
            "type": f"{value.__class__.__module__}.{value.__class__.__name__}",
            "repr": repr(value),
        }
