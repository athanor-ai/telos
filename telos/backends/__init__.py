"""telos.backends — one module per verifier.

Each backend exposes:
    compile(ir: ProtocolIR, out_dir: Path) -> list[Path]
    verify(artefacts: list[Path]) -> Verdict

v0.1 status: stubs. The implementation lands in the Week 2
milestone; see docs/roadmap.md.
"""
