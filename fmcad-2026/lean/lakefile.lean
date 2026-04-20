import Lake
open Lake DSL

package «bbr3-starvation» where
  leanOptions := #[
    ⟨`pp.unicode.fun, true⟩,
    ⟨`autoImplicit, false⟩
  ]

require mathlib from git
  "https://github.com/leanprover-community/mathlib4.git" @ "v4.14.0"

@[default_target]
lean_lib «BbrStarvation» where
  roots := #[`BbrStarvation.Basic, `BbrStarvation.Trace, `BbrStarvation.OnsetTheorem, `BbrStarvation.OnsetTheoremTrace, `BbrStarvation.Environment, `BbrStarvation.PatchedFilter, `BbrStarvation.MultiFlow, `BbrStarvation.KernelFidelity]

@[default_target]
lean_lib «CC» where
  roots := #[`CC.Cubic, `CC.Reno]
