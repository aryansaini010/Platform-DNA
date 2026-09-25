"""Renderer: Jinja2 template → Markdown (plan §4 Step 7). Layout never from model."""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TPL_DIR = Path(__file__).resolve().parents[2] / "templates"


def render(report: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(TPL_DIR)), autoescape=False,
                      undefined=StrictUndefined)
    return env.get_template("report.md.j2").render(r=report)
