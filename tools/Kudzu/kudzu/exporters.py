"""Output helpers for kudzu."""

from __future__ import annotations

from pathlib import Path


def write_wordlist(variants: list[str], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(variants)
    if content:
        content += "\n"
    output_path.write_text(content, encoding="utf-8")
    return len(variants)
