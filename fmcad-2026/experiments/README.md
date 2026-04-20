# experiments/

Scaffold for the four-layer experimental pipeline. Each subdirectory and
script is a ticket from the ATH-338 umbrella.

## Layout

```
experiments/
  b_d_grid.py                     ATH-343 CPU simulator B/D residual sweep
  hypothesis_sweep.py             ATH-342 property-test sweep
  mutation_sweep.py               ATH-344 mutation-kill tensor driver
  lean_to_sv.py                   ATH-341 SystemVerilog dual generator
  scenarios/
    clocked_ack_base.json         base scenario, tunable B/D/link knobs
    ack_agg_B{0.25,0.5,1,2,3,4}D.json  derived scenarios per B/D cell
    rtt_diverse_4flow.json        4-flow RTT-diverse baseline
  runs/                            output JSONs + CSVs per campaign (gitignored)
    YYYYMMDD-HHMMSS/
      layer1_lean_closures.json
      layer2_ebmc_verdicts.json
      layer3_hypothesis_summary.json
      layer4_sim_residuals.csv
      mutation_tensor.json
      audit_transcripts/
  figures/
    fig_residual.py               regenerates figures/fig_residual.pdf from layer4
    fig_mutation_kill.py          regenerates figures/fig_mutation_kill.pdf
```

## Execution order

1. **ATH-340** Lean closures (asabi's fleet launches; this repo's `lean/`
   project is the target).
2. **ATH-341** EBMC cross-check on the SV dual emitted by
   `experiments/lean_to_sv.py`. Uses the ATH-328 k-induction filter from
   a downstream k-induction filter.
3. **ATH-342** and **ATH-343** run in parallel after the theorem is
   stated and mechanically checked:
   * `python3 experiments/hypothesis_sweep.py --theorem starves_within
      --examples 5000 --profile ci`
   * `python3 experiments/b_d_grid.py
      --b-grid 0.25,0.5,1,2,3,4
      --d-ms 1,5,20,50,100
      --link-rate-mbps 10,100,1000,10000
      --seeds 100
      --out experiments/runs/$(date +%Y%m%d-%H%M%S)/layer4_sim_residuals.csv`
4. **ATH-344** mutation-kill tensor after layers 1-4 are populated.
5. **Final-artifact audit cross-check** on the final bundle.
6. `python3 experiments/figures/fig_residual.py` produces the headline
   figure. `python3 experiments/figures/fig_mutation_kill.py` produces
   the cross-layer kill figure.

## Simulator dependency

The packet simulator lives in a sibling repo at
the bundled congestion-control environment. Its adapter,
`root_data/eval/adapter.py`, bridges a simple student `CongestionControl`
class to the CS143-derived simulator's `CongestionController` protocol.

ACK aggregation is **not** a first-class scenario parameter in the
current CC env. `b_d_grid.py` models an ACK burst of size `B` via a
link-buffer + link-rate combination on the return path: buffer set to
`B * MTU`, rate set to the link capacity divided by `B` so `B` ACKs clump
into one window. This is an approximation; the paper's §5.5 limitations
subsection notes the approximation and its expected error bound relative
to a true clocked-ACK testbed. Section 4 of the paper includes a
preregistration statement (`experiments/preregister_clocked_ack.md`, to
be authored) of the falsifiable prediction against a future physical
testbed.

## Budget tracking

Per-run LLM spend is logged to `runs/<stamp>/cost_tracker.json`, rolled
up into the ATH-338 umbrella audit at
`audit/ATH-338-umbrella.md` under the `## Actuals` section (to be
appended after each campaign). Expected total per campaign: $9 single,
$27 N=3.
