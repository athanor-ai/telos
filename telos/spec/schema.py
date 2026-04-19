"""spec/schema.py — pydantic schema for the verification DSL.

A spec is the single source of truth for a verification project.
It names the protocol abstraction (state + parameters + transition
sub-steps), the theorems to verify (positive, negative, or both),
and the verifier-backend configurations. The DSL compiler reads a
spec and emits one file suite per backend.

The schema is deliberately narrow — it declares what the verifiers
need to know about the protocol, not how to write the protocol
itself. Inline Lean expressions are allowed for sub-step bodies;
they are passed through to the Lean 4 backend verbatim.
"""
from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


# ─── State + parameter types ─────────────────────────────────────────


class ParamDecl(BaseModel):
    """A parameter of the protocol (fixed across a trace)."""

    name: str
    type: Literal["nat", "real"]
    doc: Optional[str] = None


class StateField(BaseModel):
    """A mutable state-machine field updated by the step function."""

    name: str
    type: str  # "real", "nat", "Fin W -> real", etc. Passed through.
    doc: Optional[str] = None


# ─── Sub-steps ───────────────────────────────────────────────────────


class Substep(BaseModel):
    """One sub-step of the protocol step function.

    The substep modifies a subset of state fields. For the Lean
    backend the body is an inline Lean expression. For other
    backends the body is either re-derived from the inline
    expression or supplied via a backend-specific override.
    """

    name: str
    modifies: list[str] = Field(default_factory=list)
    inline_lean: Optional[str] = None
    inline_dafny: Optional[str] = None
    inline_sv: Optional[str] = None
    doc: Optional[str] = None


# ─── Theorem declarations ────────────────────────────────────────────


class Theorem(BaseModel):
    """A theorem statement to verify across backends.

    `kind="negative"` is a starvation / impossibility claim; the
    theorem asserts something bad MUST happen. `kind="positive"`
    is an invariant; the theorem asserts something good holds.
    """

    name: str
    kind: Literal["positive", "negative", "invariant"]
    hypotheses: list[str] = Field(default_factory=list)
    conclusion: str
    protocol_variant: Optional[str] = None  # name of a variant spec
    doc: Optional[str] = None


# ─── Verifier configs ────────────────────────────────────────────────


class Lean4Config(BaseModel):
    toolchain: str = "leanprover/lean4:v4.14.0"
    mathlib: Literal["pinned", "latest"] = "pinned"


class DafnyConfig(BaseModel):
    container: str = "ghcr.io/athanor-ai/dafny-base:2026.04.10"


class EbmcConfig(BaseModel):
    k_induction: bool = True
    bmc_bound: int = 100
    concrete_tuple: dict[str, int] = Field(
        default_factory=lambda: {"W": 4, "D": 2, "B": 7}
    )


class HypothesisConfig(BaseModel):
    examples: int = 5000
    profile: Literal["ci", "quick"] = "ci"


class CpuSimConfig(BaseModel):
    grid: dict[str, Union[list[int], list[float], str]]
    seeds: int = 100
    t_max_s: float = 60.0


class Verifiers(BaseModel):
    lean4: Optional[Lean4Config] = None
    dafny: Optional[DafnyConfig] = None
    ebmc: Optional[EbmcConfig] = None
    hypothesis: Optional[HypothesisConfig] = None
    cpu_sim: Optional[CpuSimConfig] = None


class Replication(BaseModel):
    docker_base: str = "ubuntu:22.04"
    expected_runtime_minutes: int = 15


# ─── Top-level protocol + spec ───────────────────────────────────────


class Protocol(BaseModel):
    name: str
    citation: Optional[str] = None
    state: list[StateField]
    params: list[ParamDecl]
    substeps: list[Substep]
    step_compose: list[str]

    @field_validator("step_compose")
    @classmethod
    def _substep_names_exist(cls, v: list[str], info) -> list[str]:
        # Cannot easily check against substeps here without a root-
        # validator; the compile step performs the full check.
        return v


class Spec(BaseModel):
    version: str = "0.1"
    protocol: Protocol
    theorems: list[Theorem]
    verifiers: Verifiers = Field(default_factory=Verifiers)
    replication: Replication = Field(default_factory=Replication)

    @field_validator("theorems")
    @classmethod
    def _at_least_one_theorem(cls, v: list[Theorem]) -> list[Theorem]:
        if not v:
            raise ValueError("spec must declare at least one theorem")
        return v


def load_spec(path: str) -> Spec:
    """Read a YAML spec file and validate it."""
    import yaml

    with open(path) as fh:
        raw = yaml.safe_load(fh)
    return Spec(**raw)
