"""Smoke test for the DSL spec schema."""
from pathlib import Path

from telos.spec import Spec, load_spec


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_bbrv3_starvation_loads():
    s = load_spec(str(EXAMPLES / "bbrv3-starvation.yaml"))
    assert isinstance(s, Spec)
    assert s.protocol.name == "bbrv3"
    assert len(s.protocol.state) == 8
    assert len(s.protocol.substeps) == 5
    assert len(s.theorems) == 1
    assert s.theorems[0].kind == "negative"
    assert s.verifiers.ebmc is not None
    assert s.verifiers.ebmc.concrete_tuple == {"W": 4, "D": 2, "B": 7}


if __name__ == "__main__":
    test_bbrv3_starvation_loads()
    print("ok")
