# sv/ — SystemVerilog cross-check of the starvation sandwich bound

EBMC k-induction dual of `lean/BbrStarvation/Trace.step` and the
four invariants that certify the sandwich-bound claim.

## Files

- `bbr3_trace.sv` — SystemVerilog port of `BbrStarvation.Trace.step`
  as a single `always_ff @(posedge clk)` block. Abstractions vs the
  Lean source are documented in the file header; the load-bearing
  sub-step (`bandwidth_update` with windowed max filter) is preserved
  byte-for-byte in semantics.
- `bbr3_invariants.sv` — SVA wrapper with four invariants mapping to
  the Lean lemmas, plus the scheduler + parameter assumptions.
- `ebmc_k_induction.log` — inductive-proof output (all 4 PROVED).
- `ebmc_bmc_bound100.log` — bounded-model-checking output at `k=100`.

## What's checked

| SVA assertion | Lean lemma | EBMC result |
|---|---|---|
| `p_pacing_matches_bw_max` | `bandwidth_update` correctness | PROVED |
| `p_filter_zero_implies_pacing_zero` | drain half of `minrtt_monotone` | PROVED |
| `p_onset_upper_bound` | `onset_upper_bound` (Lemma 4) | PROVED |
| `p_filter_any_nonzero_implies_pacing_nonzero` | lower-bound core | PROVED |

All four pass both bounded model-checking at `k=100` and unconditional
k-induction (`UNSAT: inductive proof successful`). The k-induction
result is strictly stronger: it certifies the property holds at all
times, not just within 100 cycles.

## Parameterisation

The SV dual is verified at a concrete parameter tuple chosen so that
(a) the hypothesis `B > 2*D` holds, and (b) `ONSET_TIME` is small
enough for k-induction to converge fast:

- `W = 4` (filter window)
- `D = 2` (equilibrium path delay)
- `B = 7` (ACK-aggregation burst; `7 > 2*2 = 4` ✓)
- `C_MAX = W = 4` (per Lemma 7 `c_bounded_by_W`)
- `ONSET_TIME = (B/D - 2)*W + C_MAX = 1*4 + 4 = 8`

The Lean proof treats `W`, `D`, `B`, `c` as universally quantified
natural numbers; the SV dual is a refinement check at one concrete
tuple. Together with the Lean proof, this gives a two-verifier
cross-check: if the sandwich bound failed at this parameter tuple,
EBMC would find the counterexample trace; if the bound held at this
tuple but failed elsewhere, the Lean proof would refuse to close.

## Reproduce

```
ebmc sv/bbr3_invariants.sv sv/bbr3_trace.sv --top bbr3_invariants \
     --k-induction --bound 100
ebmc sv/bbr3_invariants.sv sv/bbr3_trace.sv --top bbr3_invariants \
     --bound 100
```

Tested against EBMC 5.10. Both runs complete in well under a second.

## Five-system cross-check coordination

Paper §5.5 collates verifier witnesses across five independent
backends for the same sandwich-bound statement:

1. **Lean 4** (`lean/BbrStarvation/`) — pen-and-paper proof scaffold,
   discharged by hand with Mathlib tactics.
2. **Hypothesis** (`experiments/hypothesis_sweep.py`) — property-based
   testing at the Python algebra level.
3. **Packet simulator** (`experiments/b_d_grid.py`) — empirical
   residual sweep against the closed form.
4. **EBMC k-induction** (this directory) — symbolic inductive proof
   on a SystemVerilog refinement.
5. **Dafny + SMT** (`dafny/BBRv3Trace.dfy`) — independent cross-check
   with a different tactic language (Z3 backend).

If all five agree, the sandwich bound has an unusually dense dual.
