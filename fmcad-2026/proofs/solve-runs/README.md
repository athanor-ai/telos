# Solve-run artefacts

Per-CCA artefacts from the solve pipeline referenced from Table III of
`main.tex`. Each subdirectory holds one CCA's patched SystemVerilog
plus the winning builder identity.

## Contents

- `telos_reno/` — patched SV restoring the `cwnd_floor` safety rail on
  the loss branch. Verified 3/3 PROVED at EBMC k=10 under the hw-cbmc
  scoring harness.
- `telos_cubic/` — patched SV clamping the multiplicative-decrease
  branch to at least 1 MSS. Verified 3/3 PROVED at EBMC k=10 under the
  same harness.

Each `*_patched.sv` is the SystemVerilog produced under the
banned-tactic + no-assertion-body-edit discipline. `winner.txt`
records the winning builder.
