"""Startup banner for Tramontane services."""

import sys
from typing import Literal

ServiceName = Literal["api", "worker"]

_API_LOGO = r"""
  ▀█▀ █▀█ ▄▀█ █▀▄▀█ █▀█ █▄ █ ▀█▀ ▄▀█ █▄ █ █▀▀
   █  █▀▄ █▀█ █ ▀ █ █▄█ █ ▀█  █  █▀█ █ ▀█ ██▄"""

_SERVICE_HEADERS: dict[ServiceName, str] = {
    "worker": "Tramontane · Worker",
}

WIDTH = 48
SEP = "─" * WIDTH


def print_banner(
    service: ServiceName,
    *,
    sections: list[tuple[str, list[tuple[str, str]]]],
    version: str = "0.1.0",
) -> None:
    """Print startup banner with grouped component status."""
    lines: list[str] = []

    if service == "api":
        lines.append(_API_LOGO)
        lines.append(f"  API Server v{version}".center(WIDTH))
    else:
        header = _SERVICE_HEADERS[service]
        lines.append("")
        lines.append(f"  {header}")

    lines.append(SEP)

    for section_name, items in sections:
        lines.append(f"  {section_name}")
        for name, value in items:
            lines.append(f"    {name:<26} {value}")
        lines.append("")

    lines.append(SEP)
    lines.append("")

    sys.stderr.write("\n".join(lines) + "\n")
    sys.stderr.flush()


def print_service_line(service: ServiceName) -> None:
    """Print a minimal one-line startup marker for standalone processes."""
    header = _SERVICE_HEADERS[service]
    sys.stderr.write(f"\n  {header}\n{SEP}\n\n")
    sys.stderr.flush()
