"""Typer CLI. Safe by default: every external action is dry-run unless ``--apply``.

``--apply`` alone is never sufficient for a real send — a human approval gate is
enforced at the batch level (docs/adr/0002). External integrations (Apollo, email)
are intentionally NOT wired up in this foundation.
"""

from __future__ import annotations

from dataclasses import dataclass

import typer

from spindle_gtm import __version__
from spindle_gtm.compliance import GateContext, compliance_gate
from spindle_gtm.region_policy import load_region_policies

app = typer.Typer(
    help="spindle-gtm — research accounts, gate compliance, human-approved sends.",
    no_args_is_help=True,
    add_completion=False,
)


@dataclass
class State:
    apply: bool = False


@app.callback()
def main(
    ctx: typer.Context,
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Execute external actions. Omitted = dry-run (safe default).",
    ),
) -> None:
    ctx.obj = State(apply=apply)


def _guard_external(ctx: typer.Context, action: str) -> bool:
    """Return True only if the user explicitly opted into execution with --apply."""
    state: State = ctx.obj
    if not state.apply:
        typer.echo(f"[dry-run] would {action}. Re-run with --apply to execute.")
        return False
    return True


@app.command()
def version() -> None:
    """Print the version."""
    typer.echo(__version__)


@app.command()
def regions() -> None:
    """List the seeded region compliance policies."""
    for code, policy in sorted(load_region_policies().items()):
        typer.echo(
            f"{code:3} cold_email={policy.cold_email_allowed.value:8} "
            f"consent={policy.requires_consent!s:5} basis={policy.legal_basis}"
        )


@app.command()
def gate(
    region_code: str = typer.Argument(..., help="Region code, e.g. US, CA, UK, EU, IN, KR, JP."),
    channel: str = typer.Option("email", help="email | linkedin_manual"),
    lawful_basis: bool = typer.Option(False, help="A documented lawful basis exists."),
    unsubscribe: bool = typer.Option(False, help="Unsubscribe mechanism present."),
    physical_address: bool = typer.Option(False, help="Physical postal address present."),
) -> None:
    """Evaluate the compliance gate for a hypothetical contact (read-only)."""
    result = compliance_gate(
        GateContext(
            region_code=region_code.upper(),
            channel=channel,
            has_lawful_basis=lawful_basis,
            has_unsubscribe=unsubscribe,
            has_physical_address=physical_address,
        ),
        load_region_policies(),
    )
    verdict = "PASS" if result.passed else "HOLD"
    typer.echo(f"{verdict}: {result.reason}")


@app.command()
def ingest(ctx: typer.Context) -> None:
    """Ingest the Apollo seed company list (Phase 1). External + human-approved."""
    if not _guard_external(ctx, "ingest the Apollo seed list (read-only)"):
        return
    typer.secho(
        "Apollo ingest is not wired up in this foundation. "
        "Connect Apollo (read-only) and implement Phase 1 before using --apply.",
        fg=typer.colors.YELLOW,
    )
    raise typer.Exit(code=1)


@app.command()
def send(ctx: typer.Context) -> None:
    """Send an approved batch (Phase 4). External + human-approved + capped."""
    if not _guard_external(ctx, "send the approved batch"):
        return
    typer.secho(
        "Sending is not wired up in this foundation. A batch-level human approval "
        "gate and deliverability preflight are required before any send.",
        fg=typer.colors.YELLOW,
    )
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
