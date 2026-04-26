## What made `.asc` work

## 1) Correct filter component values
For first-order HP + LP around universal op-amp:
- High-pass corner near 50 Hz:
  - `CHP VIN NHP 100n`
  - `RHP NHP 0 31.8k`
  - because `f_c = 1/(2*pi*R*C)`
- Low-pass corner near 20 kHz:
  - `RLP NHP NBP 7.96k`
  - `CLP NBP 0 1n`

## 2) Correct op-amp model usage
Working universal op-amp instance text:
- `XU_BP NBP VBP VCC VEE VBP level1 Avol=1Meg GBW=10Meg ...`
- plus library include in netlist generation:
  - `.lib UniversalOpAmp1.lib`

## 3) Proper AC stimulus and analysis command
- Source includes AC small-signal amplitude:
  - `SYMATTR Value2 AC 1 0`
- AC sweep command present:
  - `.ac dec 200 1 1Meg`

## 4) Measurement syntax that works in LTspice
Working form:
- `.meas AC FL WHEN mag(V(VBP))=GMAX/sqrt(2) RISE=1`
- `.meas AC FH WHEN mag(V(VBP))=GMAX/sqrt(2) FALL=last`

## What made `.asc` fail or produce misleading outcomes

## A) Wrong invocation path (tool/API usage issue)
Using `execute {"api_name":"run","inputs":{"object_name":"<AscEditor object>"}}` returned `simulation failed!` in this environment, even for known-good schematics.

What worked reliably:
1. Create `SimRunner` with output folder in current dir.
2. `run` with the schematic file path.
3. `wait_completion`.

So this failure was not necessarily the `.asc` content itself.

## B) Incorrect `.meas` expression form (result interpretation issue)
Earlier form using `TRIG ...` for AC corner extraction produced nonsensical corner readings near the top of sweep range.

Example problematic form:
- `.meas AC FL TRIG mag(V(...))=GMAX/sqrt(2) RISE=1`

Working corrected form:
- `.meas AC FL WHEN mag(V(...))=GMAX/sqrt(2) RISE=1`

## C) Floating/unconnected symbol pins (topology issue)
Some generated netlists show nodes like `NC_01` (unconnected pin). LTspice can still run, but the circuit may not be what you intended.

Example from netlist:
- `R1 VI NC_01 7.96k`  (one side floating)

This does not always crash simulation, but it can silently change filter behavior.

## D) Typical LTspice op-amp symbol pitfall
`opamp2` symbol without a linked model/subckt often fails (missing model). `UniversalOpAmp`/`UniversalOpAmp1` with proper params/library is safer for generic designs.

## Practical checklist for future `.asc` files
1. Ensure every intended component terminal is actually wired (no unintended `NC_*` nodes).
2. Ensure op-amp has valid model backing (`UniversalOpAmp1.lib` or a real `.lib/.subckt`).
3. Include AC drive (`AC 1`) and the desired `.ac` command.
4. Use `.meas ... WHEN ...` for AC crossing frequencies.
5. Run through `SimRunner` and check the `.log` values, not only waveform plots.
