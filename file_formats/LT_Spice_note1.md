# note1.md - LTspice `.asc` validity notes (from this run)

## 1) Valid `.asc` pattern that worked in this run

This schematic ran successfully through `ltspice_mcp` using:
1. `AscEditor` on the `.asc` file
2. `SimRunner` with output folder `/tmp/test/sim_precision`
3. `run(netlist="/tmp/test/precision_led_10mA.asc")`
4. `wait_completion`

### Key text that made the `.asc` valid

A directive-only schematic was used. In LTspice `.asc`, directive lines must be `TEXT ... !<spice line>`.

Critical working directives:
- `!.param ILED=10m`
- `!.param VREF=2.5`
- `!.param RSENSE={VREF/ILED}`
- `!VCC VCC 0 12`
- `!VREFSRC NREF 0 {VREF}`
- `!VLED VCC NLED 5`
- `!M1 ND NG NS 0 NM1`
- `!RS NS 0 {RSENSE}`
- `!BERR NG 0 V=limit(1e6*(V(NREF)-V(NS)),0,12)`
- `!.model NM1 NMOS (VTO=2.2 KP=0.5 RS=0.1 RD=0.1 LAMBDA=0.02)`
- `!.op`
- `!.meas ...`

Why these matter:
- `!.op` is required for DC operating-point simulation.
- `.model NM1 ...` is required because `M1` references model `NM1`.
- `BERR` creates feedback to force `V(NS)` to `VREF`, so `I_LED ~= VREF/RSENSE`.

## 2) Measured result from this run

From `/tmp/test/sim_precision/precision_led_10mA_1.log`:
- `-I(VLED) = -0.00999998021871 A`
- Current magnitude = `9.99998021871 mA`
- Error vs 10 mA = `-0.000197813%`

This satisfies the 0.1% steady-state requirement in simulation.

## 3) `.asc` content that is valid but can mislead results

### A) Wrong current sign in `.meas`
- Initial measure used `-I(VLED)` and interpreted sign incorrectly.
- Simulation was correct; measurement expression/sign convention was wrong.
- Fix: use magnitude: `abs(I(VLED))` in `.meas`.

### B) Convergence warnings are not always failure
- Log showed Gmin stepping failure, then source stepping succeeded.
- This is still a valid simulation if final status is completed and measurements are present.

## 4) Common invalid `.asc`/flow patterns (and why they fail)

### A) Missing analysis directive
- If `.op`, `.tran`, `.ac`, etc. is absent, LTspice has no requested analysis.
- Result: no useful simulation output.

### B) Missing model/subcircuit for used symbol/device
- Example: using MOSFET or op-amp symbol requiring a model, but no `.model` or `.lib/.include`.
- Result: model/subckt errors at netlist/simulation stage.

### C) Non-directive text where directive is intended
- In `.asc`, commands in `TEXT` must start with `!` to become netlist directives.
- Without `!`, the line is annotation/comment only.

### D) Unsupported path/file type in MCP read APIs
- `AscEditor` supports `.asc/.net/.cir` paths.
- Wrong extension/path gives file/type validation errors before sim starts.

### E) Running on wrong object type/method path in MCP flow
- Reliable flow in this environment: create `SimRunner`, then call `run` on the `SimRunner` object with a netlist/path, then `wait_completion`.

## 5) MCP server tool/API calls: worked vs failed in this run

MCP server used: `ltspice_mcp`

### 5.1 Calls that worked

Tool calls that completed with usable results:
1. `runtime_info {}` -> confirmed simulator configured.
2. `stop_reset {}` -> completed (after polling `execute_status`).
3. `execute {"api_name":"AscEditor","inputs":{"new_object_name":"asc1","asc_file":"/tmp/test/precision_led_10mA.asc"}}`
4. `execute {"api_name":"SimRunner","inputs":{"new_object_name":"runner1","output_folder":"/tmp/test/sim_precision"}}`
5. `execute {"api_name":"run","inputs":{"object_name":"runner1","netlist":"/tmp/test/precision_led_10mA.asc"}}`
6. `execute {"api_name":"wait_completion","inputs":{"object_name":"runner1"}}`
7. `execute_status {}` polls during queued operations.

### 5.2 Calls that failed/cancelled

In this run, no LTspice API-level error like `invalid input!`, `file not found!`, or `simulation failed!` was returned for the final successful flow.

Two MCP tool invocations were cancelled by the orchestration safety layer (not by LTspice parser/simulator logic):
1. One `execute` call for `AscEditor` was cancelled once, then re-issued successfully.
2. One `execute` call for `SimRunner` was cancelled once; final run used a previously created runner and succeeded.

Meaning: these cancellations were tooling/orchestration interruptions, not `.asc` syntax failures.

## 6) LTspice keywords/text patterns: worked vs failed (from this experience)

### 6.1 Keywords/text that worked

Structural `.asc` keywords:
- `Version`
- `SHEET`
- `TEXT` (with `!` for directives)

SPICE directives and element cards that worked:
- `.param`
- `.model`
- `.op`
- `.meas OP ...`
- `V...` independent voltage sources
- `R...` resistors
- `C...` capacitor
- `M...` MOSFET instance
- `B...` behavioral source

Working measurement forms:
- `.meas OP ILED_MEAS PARAM abs(I(VLED))`
- `.meas OP IERR_PCT PARAM 100*((abs(I(VLED))-{ILED})/{ILED})`

### 6.2 Keywords/text that failed or were problematic

No hard parser keyword rejection occurred in the final successful schematic.

Problematic text patterns observed:
1. Measurement sign convention issue:
   - Old form: `.meas OP ... FIND -I(VLED)`
   - This did not fail parsing, but produced a misleading signed value for interpretation.
   - Better for pass/fail checking: use `abs(I(...))` for magnitude.
2. `TEXT` without leading `!` for SPICE content:
   - Not a parser crash, but LTspice treats it as annotation, not as executable netlist directive.
   - Effectively fails simulation intent because intended command is ignored.
3. Missing mandatory directives/models:
   - Missing `.op`/`.tran`/`.ac` causes no requested analysis.
   - Missing `.model`/`.lib` for referenced devices causes simulation/netlist errors.

## 7) Practical checklist for future valid LTspice `.asc`

1. Keep all node names and element references consistent.
2. Ensure every active device has a valid model (`.model`, `.include`, or `.lib`).
3. Include at least one explicit analysis command (`.op/.tran/.ac/.dc/...`).
4. For directive-only schematics, every SPICE line in `TEXT` starts with `!`.
5. In MCP, use `AscEditor` + `SimRunner.run(...)` + `wait_completion` and inspect `.log` measures.
6. Validate measurement sign conventions (or use absolute value where direction is arbitrary).
