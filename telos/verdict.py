"""verdict.py — verifier verdict model + sandwich-bound reconciliation.

Each backend returns a `Verdict`; `telos verify` collects them,
reconciles into a joint sandwich bound, and prints a one-page report.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class Verdict:
    verifier: str
    theorem: str
    status: Literal["closed", "outlined", "failed", "skipped"]
    wall_time_s: float = 0.0
    evidence_path: Optional[str] = None
    sorry_count: Optional[int] = None
    message: str = ""


@dataclass
class Reconciliation:
    theorem: str
    per_verifier: list[Verdict] = field(default_factory=list)

    @property
    def closed_by(self) -> list[str]:
        return [v.verifier for v in self.per_verifier if v.status == "closed"]

    @property
    def failed_by(self) -> list[str]:
        return [v.verifier for v in self.per_verifier if v.status == "failed"]

    @property
    def is_sandwich(self) -> bool:
        """A theorem is sandwich-bounded when >= 2 independent
        verifiers close it AND none fails."""
        return len(self.closed_by) >= 2 and not self.failed_by


def render_report(recons: list[Reconciliation]) -> str:
    """Render a human-readable report matching the paper's sandwich-
    bound claim format."""
    out = []
    out.append("=" * 60)
    out.append("telos verify — sandwich-bound report")
    out.append("=" * 60)
    for r in recons:
        out.append(f"\n[{r.theorem}]")
        for v in r.per_verifier:
            status_glyph = {
                "closed": "✓",
                "outlined": "…",
                "failed": "✗",
                "skipped": "-",
            }.get(v.status, "?")
            line = f"  {status_glyph} {v.verifier:12s}  {v.status:10s}  {v.wall_time_s:5.1f}s"
            if v.sorry_count is not None:
                line += f"  sorry={v.sorry_count}"
            if v.message:
                line += f"  {v.message}"
            out.append(line)
        if r.is_sandwich:
            out.append(f"  SANDWICH: closed by {len(r.closed_by)} "
                       f"backend(s) [{', '.join(r.closed_by)}]")
        elif r.failed_by:
            out.append(f"  DISAGREEMENT: {len(r.failed_by)} failure(s) "
                       f"[{', '.join(r.failed_by)}]")
        else:
            out.append("  INCOMPLETE: < 2 closed; consider adding verifiers")
    return "\n".join(out)
