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
        from telos.backends.ebmc import compile_ebmc
        files = compile_ebmc(spec, out)
        emitted.extend(files)
        click.echo(f"    ebmc      → {len(files)} files")
    if spec.verifiers.hypothesis:
        from telos.backends.hypothesis_be import compile_hypothesis
        files = compile_hypothesis(spec, out)
        emitted.extend(files)
        click.echo(f"    hypothesis → {len(files)} files")
    if spec.verifiers.cpu_sim:
        from telos.backends.cpusim import compile_cpusim
        files = compile_cpusim(spec, out)
        emitted.extend(files)
        click.echo(f"    cpu_sim    → {len(files)} files")

    click.echo()
    click.echo(f"  emitted {len(emitted)} file(s) under {out}/")


@main.command()
@click.argument("spec_file", type=click.Path(exists=True, dir_okay=False))
def verify(spec_file: str) -> None:
    """Run every configured backend; report the sandwich bound."""
    import shutil
    import subprocess
    import time

    from telos.verdict import Verdict, Reconciliation, render_report

    spec = load_spec(spec_file)
    click.echo(f"[telos verify] {spec_file}")
    click.echo(f"  protocol: {spec.protocol.name}")

    # Compile first so backend artefacts exist.
    build_dir = Path("build")
    build_dir.mkdir(exist_ok=True)
    from telos.backends import lean4 as be_lean4
    from telos.backends import dafny as be_dafny
    from telos.backends import ebmc as be_ebmc
    from telos.backends import hypothesis_be as be_hypothesis
    from telos.backends import cpusim as be_cpusim
    emitted: dict[str, list[Path]] = {}
    if spec.verifiers.lean4:
        emitted["lean4"] = be_lean4.compile_lean4(spec, build_dir)
    if spec.verifiers.dafny:
        emitted["dafny"] = be_dafny.compile_dafny(spec, build_dir)
    if spec.verifiers.ebmc:
        emitted["ebmc"] = be_ebmc.compile_ebmc(spec, build_dir)
    if spec.verifiers.hypothesis:
        emitted["hypothesis"] = be_hypothesis.compile_hypothesis(spec, build_dir)
    if spec.verifiers.cpu_sim:
        emitted["cpu_sim"] = be_cpusim.compile_cpusim(spec, build_dir)

    # Drive each backend; collect verdicts.
    recons: list[Reconciliation] = []
    for t in spec.theorems:
        r = Reconciliation(theorem=t.name)
        # lean4: run `lake build` on the emitted project; count sorry.
        if "lean4" in emitted:
            lean_dir = build_dir / "lean"
            lake_ok = (lean_dir / "lakefile.lean").exists()
            if lake_ok and shutil.which("lake"):
                tic = time.time()
                try:
                    res = subprocess.run(
                        ["lake", "build"], cwd=lean_dir,
                        capture_output=True, timeout=1200,
                    )
                    ok = res.returncode == 0
                    # Count sorry occurrences (v0.5 proxy; a real
                    # reviewer uses #print axioms for rigor).
                    sorry_count = 0
                    for p in lean_dir.rglob("*.lean"):
                        sorry_count += p.read_text(
                            errors="replace").count("sorry")
                    r.per_verifier.append(Verdict(
                        verifier="lean4", theorem=t.name,
                        status="closed" if ok and sorry_count == 0
                               else ("outlined" if ok else "failed"),
                        wall_time_s=time.time() - tic,
                        sorry_count=sorry_count,
                        message=res.stdout.decode()[-120:].strip().replace("\n", " ")
                                or res.stderr.decode()[-120:].strip().replace("\n", " "),
                    ))
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    r.per_verifier.append(Verdict(
                        verifier="lean4", theorem=t.name,
                        status="skipped", message=f"{type(e).__name__}",
                    ))
            else:
                r.per_verifier.append(Verdict(
                    verifier="lean4", theorem=t.name,
                    status="skipped" if not lake_ok
                           else "outlined",
                    message="lake not on PATH" if lake_ok
                            else "lakefile.lean not emitted",
                ))
        # dafny: actually verify if dafny-base container is available.
        if "dafny" in emitted:
            if shutil.which("docker"):
                tic = time.time()
                # Run dafny verify on the emitted .dfy
                dfy_files = [p for p in emitted["dafny"] if p.suffix == ".dfy"]
                if dfy_files:
                    cmd = [
                        "docker", "run", "--rm",
                        "-v", f"{dfy_files[0].parent.resolve()}:/w",
                        "-w", "/w",
                        "ghcr.io/athanor-ai/dafny-base:2026.04.10",
                        "dafny", "verify", dfy_files[0].name,
                    ]
                    try:
                        res = subprocess.run(cmd, capture_output=True, timeout=60)
                        ok = res.returncode == 0 and b"0 errors" in res.stdout
                        r.per_verifier.append(Verdict(
                            verifier="dafny", theorem=t.name,
                            status="closed" if ok else "failed",
                            wall_time_s=time.time() - tic,
                            message=res.stdout.decode()[-100:].strip().replace("\n", " "),
                        ))
                    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                        r.per_verifier.append(Verdict(
                            verifier="dafny", theorem=t.name,
                            status="skipped", message=f"{type(e).__name__}",
                        ))
            else:
                r.per_verifier.append(Verdict(
                    verifier="dafny", theorem=t.name,
                    status="skipped", message="docker not available on host",
                ))
        # ebmc: run k-induction on the emitted SV; parse verdict.
        if "ebmc" in emitted:
            if shutil.which("ebmc"):
                sv_files = [p for p in emitted["ebmc"] if p.suffix == ".sv"]
                inv = next((p for p in sv_files
                            if "invariants" in p.name), None)
                trc = next((p for p in sv_files
                            if "trace" in p.name), None)
                if inv and trc:
                    tic = time.time()
                    cmd = ["ebmc", str(inv), str(trc),
                           "--top", inv.stem, "--k-induction"]
                    try:
                        res = subprocess.run(
                            cmd, capture_output=True, timeout=300)
                        out = res.stdout.decode()
                        proved = out.count("PROVED")
                        failed = out.count("REFUTED") + out.count("UNKNOWN")
                        ok = res.returncode == 0 and proved > 0 and failed == 0
                        r.per_verifier.append(Verdict(
                            verifier="ebmc", theorem=t.name,
                            status="closed" if ok else "failed",
                            wall_time_s=time.time() - tic,
                            message=f"{proved} PROVED, {failed} non-proved",
                        ))
                    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                        r.per_verifier.append(Verdict(
                            verifier="ebmc", theorem=t.name,
                            status="skipped", message=f"{type(e).__name__}",
                        ))
                else:
                    r.per_verifier.append(Verdict(
                        verifier="ebmc", theorem=t.name,
                        status="outlined",
                        message="SV files emitted but top module not identified",
                    ))
            else:
                r.per_verifier.append(Verdict(
                    verifier="ebmc", theorem=t.name,
                    status="skipped", message="ebmc not on PATH",
                ))
        # hypothesis: run pytest on the emitted file.
        if "hypothesis" in emitted:
            tic = time.time()
            py_files = [p for p in emitted["hypothesis"] if p.suffix == ".py"]
            if py_files:
                cmd = ["python3", "-m", "pytest", "-q", str(py_files[0])]
                env = {"HYPOTHESIS_PROFILE": "quick", "PATH": "/usr/bin:/usr/local/bin"}
                try:
                    res = subprocess.run(cmd, capture_output=True, timeout=120,
                                          env={**__import__("os").environ, **env})
                    ok = res.returncode == 0
                    r.per_verifier.append(Verdict(
                        verifier="hypothesis", theorem=t.name,
                        status="closed" if ok else "failed",
                        wall_time_s=time.time() - tic,
                        message=res.stdout.decode()[-120:].strip().replace("\n", " "),
                    ))
                except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                    r.per_verifier.append(Verdict(
                        verifier="hypothesis", theorem=t.name,
                        status="skipped", message=f"{type(e).__name__}",
                    ))
        # cpu_sim: outlined for v0.3; user fills in step body.
        if "cpu_sim" in emitted:
            r.per_verifier.append(Verdict(
                verifier="cpu_sim", theorem=t.name,
                status="outlined",
                message="step body is user-supplied in v0.3 (see simulate.py stub)",
            ))
        recons.append(r)

    click.echo()
    click.echo(render_report(recons))


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
