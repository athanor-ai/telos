"""telos.cli — command-line entry point for the DSL."""
from __future__ import annotations

import sys
from pathlib import Path

import click

from telos.spec import load_spec


@click.group()
@click.version_option()
def main() -> None:
    """telos — machine-checked congestion-control verification."""


@main.command()
@click.argument("spec_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--out",
    "out_dir",
    type=click.Path(file_okay=False),
    default="build",
    help="Output directory for compiled backend artefacts.",
)
def compile(spec_file: str, out_dir: str) -> None:
    """Compile a spec into per-backend artefacts."""
    spec = load_spec(spec_file)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    click.echo(f"[telos compile] {spec_file} → {out_dir}/")
    click.echo(f"  protocol: {spec.protocol.name}")
    click.echo(
        f"  {len(spec.theorems)} theorem(s), {len(spec.protocol.substeps)} substep(s)"
    )

    emitted: list[Path] = []
    if spec.verifiers.lean4:
        from telos.backends.lean4 import compile_lean4
        files = compile_lean4(spec, out)
        emitted.extend(files)
        click.echo(f"    lean4     → {len(files)} files")
    if spec.verifiers.dafny:
        from telos.backends.dafny import compile_dafny
        files = compile_dafny(spec, out)
        emitted.extend(files)
        click.echo(f"    dafny     → {len(files)} files")
    if spec.verifiers.ebmc:
        click.echo("    ebmc      → [v0.2 stub; see telos/backends/ebmc.py]")
    if spec.verifiers.hypothesis:
        click.echo("    hypothesis → [v0.2 stub]")
    if spec.verifiers.cpu_sim:
        click.echo("    cpu_sim    → [v0.2 stub]")

    click.echo()
    click.echo(f"  emitted {len(emitted)} file(s) under {out}/")


@main.command()
@click.argument("spec_file", type=click.Path(exists=True, dir_okay=False))
def verify(spec_file: str) -> None:
    """Run every configured backend; report the sandwich bound."""
    spec = load_spec(spec_file)
    click.echo(f"[telos verify] {spec_file}")
    click.echo(f"  protocol: {spec.protocol.name}")
    click.echo(f"  theorems: {[t.name for t in spec.theorems]}")
    click.echo()
    click.echo("  [0.1] verify pipeline not yet wired; see docs/roadmap.md.")
    click.echo("        backend modules under telos/backends/ are stubs")
    click.echo("        pending compile-to-artefact logic for each verifier.")


@main.command()
@click.argument("spec_file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--out",
    "out_path",
    type=click.Path(dir_okay=False),
    default="replication.tar.gz",
    help="Replication-package tarball output path.",
)
def pack(spec_file: str, out_path: str) -> None:
    """Package the spec + backend artefacts + Dockerfile into a
    tarball that a reviewer can reproduce the theorem from."""
    spec = load_spec(spec_file)
    click.echo(f"[telos pack] {spec_file} → {out_path}")
    click.echo(f"  protocol: {spec.protocol.name}")
    click.echo("  [0.1] packaging not yet wired; see docs/roadmap.md.")


if __name__ == "__main__":
    main()
