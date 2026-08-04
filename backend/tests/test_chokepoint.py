"""The architectural claim of the whole project, checked directly: nothing
outside Sentinel calls a registered tool's implementation. If this test ever
needs to be weakened to pass, that is a sign the chokepoint has been broken,
not a sign the test was wrong."""

from pathlib import Path

AEGIS_ROOT = Path(__file__).resolve().parent.parent / "aegis"
ALLOWED_CALLERS = {AEGIS_ROOT / "sentinel" / "core.py"}


def test_only_sentinel_core_calls_tool_fn():
    offenders = []
    for path in AEGIS_ROOT.rglob("*.py"):
        if path in ALLOWED_CALLERS or path.parts[-2:] == ("tools", "registry.py"):
            continue
        text = path.read_text()
        if "tool.fn(" in text or ".fn(**arguments)" in text:
            offenders.append(str(path))

    assert offenders == [], f"Found direct tool execution outside Sentinel.guard: {offenders}"
