# LLM Tool-Calling Guide (OpenCode, Claude Code, OpenAI Codex)

## Core MCP Tools
| Tool | Input | Purpose |
|---|---|---|
| `runtime_info` | `{}` | Queue runtime diagnostics for LTspice/Wine/OS and simulator readiness. |
| `execute_status` | `{}` | Poll latest status for the session queue. |
| `stop_reset` | `{}` | Cancel/reset queue and object registry for current session. |
| `execute` | `{"api_name": "...", "inputs": {...}}` | Queue one PyLTSpice API operation. |

## Async Behavior
1. Call `runtime_info`, `stop_reset`, or `execute`.
2. Immediate response: `performing LTspice operation in progress`.
3. Poll with `execute_status` until status is not in-progress.
4. Read `output` and optional `output_obj_name` on completion.

## Standard Response Shapes
In progress:
```json
{"status":"performing LTspice operation in progress","operation":"execute"}
```
Completed:
```json
{"status":"LTspice operation completed!","operation":"execute","output_obj_name":"obj1","output":{}}
```
Error statuses:
- `invalid input!`
- `file not found!`
- `unsupported file type!`
- `simulator not configured!`
- `simulation failed!`
- `parser failed!`
- `LTspice operation timed out!`
- `internal error`

## `execute` API Names
`inputs.new_object_name` may be provided to store newly created objects.

| api_name | Typical inputs | Description |
|---|---|---|
| `all_loggers` | none | Return logger names used by PyLTSpice stack. |
| `set_log_level` | `level:int` | Set global logging level. |
| `add_log_handler` | `handler_type:"null"|"stream"` | Add handler to known loggers. |
| `RawRead` | `raw_filename`, `traces_to_read?`, `dialect?`, `verbose?` | Read LTspice RAW file. |
| `LTSpiceRawRead` | same as `RawRead` | Alias of `RawRead`. |
| `RawWrite` | `**kwargs` | Build/write LTspice RAW content. |
| `Trace` | `name`, `data`, `whattype?` | Create RAW trace. |
| `SpiceCircuit` | `netlist source/path` | Generic spice circuit API. |
| `SpiceEditor` | `netlist_file`, `encoding?`, `create_blank?` | Netlist editor. |
| `AscEditor` | `asc_file`, `encoding?` | LTspice ASC editor. |
| `SimRunner` | `simulator?`, `parallel_sims?`, `timeout?`, `verbose?`, `output_folder?` | Batch runner. |
| `SimCommander` | `netlist_file`, `parallel_sims?`, `timeout?`, `verbose?`, `encoding?`, `simulator?` | Legacy editor+runner. |
| `LTspice` | none | Return LTspice simulator class. |
| `LTSpiceLogReader` | `log_filename`, `read_measures?`, `step_set?` | Parse LTspice log step/measure data. |
| `reformat_LTSpice_export` | `input_file`, `output_file?` | Reformat export text. |
| `LTSpiceExport` | `export_filename` | Parse LTspice export file. |
| `LogfileData` | ctor args | Generic logfile dataset holder. |
| `LTComplex` | ctor args | Complex-value wrapper. |
| `opLogReader` | `filename` | Parse op-point log sections. |
| `ProcessCallback` | ctor args | Callback base class. |
| `SimStepper` | `circuit`, `runner` | Parameter/model sweep controller. |
| `Montecarlo` | `circuit_file`, `runner` | Monte Carlo analysis toolkit. |
| `WorstCaseAnalysis` | `circuit_file`, `runner` | Worst-case analysis toolkit. |
| `sweep` | `stop` OR `start,stop,step` | Linear sweep iterator. |
| `sweep_n` | `start,stop,n` | Linear sweep fixed points. |
| `sweep_log` | `start,stop,step_factor/base` | Logarithmic sweep iterator. |
| `sweep_log_n` | `start,stop,n` | Logarithmic sweep fixed points. |
| `sweep_iterators` | none | Multi-parameter sweep helper object. |
| `EncodingDetectError` | ctor args | Encoding exception type. |
| `detect_encoding` | `file/path`, `encodings?`, `**kwargs` | Detect text encoding. |

## Method Calls via `execute`
Server supports direct object method invocation when `inputs.object_name` is present.
Examples:
- `{"api_name":"set_tolerance","inputs":{"object_name":"mc","ref":"C","new_tolerance":0.1,"distribution":"uniform"}}`
- `{"api_name":"get_trace_names","inputs":{"object_name":"raw1"}}`
- `{"api_name":"save_netlist","inputs":{"object_name":"ed1","run_netlist_file":"/abs/path/out.net"}}`

Dotted names are also supported (e.g. `SpiceEditor.run`).

## Example Workflow
```json
{"tool":"runtime_info","arguments":{}}
```
```json
{"tool":"execute","arguments":{"api_name":"AscEditor","inputs":{"new_object_name":"sallenkey","asc_file":"/abs/path/testfiles/sallenkey.asc"}}}
```
```json
{"tool":"execute","arguments":{"api_name":"SimRunner","inputs":{"new_object_name":"runner1","output_folder":"/abs/path/temp_mc"}}}
```
```json
{"tool":"execute","arguments":{"api_name":"Montecarlo","inputs":{"new_object_name":"mc","circuit_file":"sallenkey","runner":"runner1"}}}
```
```json
{"tool":"execute","arguments":{"api_name":"set_tolerance","inputs":{"object_name":"mc","ref":"C","new_tolerance":0.1,"distribution":"uniform"}}}
```

## Integration-Test Mapping
Integration suites exercise these flows through MCP client calls:
- `tests/integration/test_examples_via_mcp.py` for all files in `PyLTSpice/examples/`
- `tests/integration/test_readme_examples_via_mcp.py` for all `-- in examples/*.py` references in `PyLTSpice/README.md`
