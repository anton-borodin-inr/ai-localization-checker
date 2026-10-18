"""CLAUDE.md and AGENTS.md carry the same rules below their first paragraph."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def shared_body(name: str) -> str:
    text = (ROOT / name).read_text(encoding="utf-8")
    # Title line, blank line, intro paragraph, blank line; the rest is shared.
    return text.split("\n", 4)[4]


def test_agent_rule_files_share_the_same_body():
    assert shared_body("CLAUDE.md") == shared_body("AGENTS.md")
