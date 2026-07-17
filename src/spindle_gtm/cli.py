"""Typer CLI. Safe by default: every external action is dry-run unless ``--apply``.

``--apply`` alone is never sufficient for a real send — a human approval gate is
enforced at the batch level (docs/adr/0002). External integrations (Apollo, email)
are intentionally NOT wired up in this foundation.
"""

from __future__ import annotations

import json
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
def doctor() -> None:
    """Read-only preflight: Apollo CLI/auth/MCP, DB, config, no PII/secrets, kill switch.

    Consumes no Apollo credits and never modifies Apollo.
    """
    from spindle_gtm.doctor import run_all

    results = run_all()
    for r in results:
        mark = "OK  " if r.ok else "FAIL"
        typer.echo(f"[{mark}] {r.name}: {r.detail}")
    failed = [r.name for r in results if not r.ok]
    if failed:
        typer.secho(f"\n{len(failed)} check(s) failed: {', '.join(failed)}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho("\nAll checks passed.", fg=typer.colors.GREEN)


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


sync_app = typer.Typer(help="Read-only Apollo synchronization.", no_args_is_help=True)
app.add_typer(sync_app, name="sync")


@sync_app.command("accounts")
def sync_accounts(
    ctx: typer.Context,
    list_name: str = typer.Option(None, "--list", help="Apollo account list name (scope label)."),
    stage: str = typer.Option(None, "--stage", help="Apollo account stage (scope label)."),
    csv_path: str = typer.Option(None, "--csv", help="Mode A: path to an Apollo CSV export."),
    workspace: str = typer.Option(None, "--workspace", help="Apollo workspace label."),
    manifest: int = typer.Option(None, "--manifest", help="Manifest id to apply."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Compute + persist a sync diff (default)."
    ),
) -> None:
    """Sync accounts from Apollo (read-only). Dry-run by default; --apply needs --manifest."""
    from pathlib import Path

    from spindle_gtm.db import session_scope
    from spindle_gtm.sync import CsvAccountSource, SyncScope, apply_sync, plan_sync

    state: State = ctx.obj
    if list_name:
        scope_type, scope_value = "list", list_name
    elif stage:
        scope_type, scope_value = "stage", stage
    elif csv_path:
        scope_type, scope_value = "csv", csv_path
    else:
        typer.secho("Provide --list, --stage, or --csv.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if not csv_path:
        typer.secho(
            "Mode A needs an export: pass --csv <apollo_export.csv>. (Mode B API sync is "
            "gated on Apollo plan/credentials and is not wired for CLI reads yet.)",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=1)

    scope = SyncScope(mode="A", scope_type=scope_type, scope_value=scope_value, workspace=workspace)
    source = CsvAccountSource(Path(csv_path), scope)

    with session_scope() as session:
        if state.apply:
            if manifest is None:
                typer.secho("--apply requires --manifest <id>.", fg=typer.colors.RED)
                raise typer.Exit(code=1)
            run = apply_sync(session, source, manifest)
            session.commit()
            typer.echo(f"applied: {run.stats_json}")
        else:
            diff, mf = plan_sync(session, source)
            session.commit()
            typer.echo(json.dumps(diff.summary(scope), indent=2))
            typer.secho(
                f"\nmanifest id: {mf.id} — apply with: --apply --manifest {mf.id}",
                fg=typer.colors.GREEN,
            )


outbound_app = typer.Typer(
    help="Apollo write gateway (the ONLY write path). Dry-run by default.", no_args_is_help=True
)
app.add_typer(outbound_app, name="outbound")


def _load_batch_and_manifests(batch_id: int):  # type: ignore[no-untyped-def]
    from sqlmodel import select

    from spindle_gtm.models import ExternalActionManifest, OutreachBatch

    def inner(session):  # type: ignore[no-untyped-def]
        batch = session.get(OutreachBatch, batch_id)
        if batch is None:
            typer.secho(f"no batch {batch_id}", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        manifests = list(
            session.exec(
                select(ExternalActionManifest).where(
                    ExternalActionManifest.batch_id == batch_id,
                    ExternalActionManifest.action_type.startswith("apollo:"),
                )
            )
        )
        return batch, manifests

    return inner


@outbound_app.command("plan")
def outbound_plan(batch: int = typer.Option(..., "--batch")) -> None:
    """Build immutable per-write manifests for the batch (no Apollo access)."""
    from spindle_gtm.apollo_gateway import default_writes_for_batch, plan_writes
    from spindle_gtm.db import session_scope

    with session_scope() as session:
        b, _ = _load_batch_and_manifests(batch)(session)
        writes = default_writes_for_batch(session, b)
        manifests = plan_writes(session, b, writes)
        session.commit()
        typer.echo(f"planned {len(manifests)} write(s) for batch {batch}")
        for m in manifests:
            typer.echo(f"  {m.action_type} idem={m.idempotency_key[:12]}…")


@outbound_app.command("verify")
def outbound_verify(batch: int = typer.Option(..., "--batch")) -> None:
    """Re-validate approval, gates, caps, IDs, and kill switch. Never writes."""
    from spindle_gtm.apollo_gateway import verify_outbound
    from spindle_gtm.db import session_scope

    with session_scope() as session:
        b, manifests = _load_batch_and_manifests(batch)(session)
        report = verify_outbound(session, b, manifests)
        session.commit()
        for err in report.errors:
            typer.echo(f"  FAIL {err}")
        if report.ok:
            typer.secho("verify OK", fg=typer.colors.GREEN)
        else:
            typer.secho(f"{len(report.errors)} check(s) failed", fg=typer.colors.RED)
            raise typer.Exit(code=1)


@outbound_app.command("apply")
def outbound_apply(
    batch: int = typer.Option(..., "--batch"),
    confirm: str = typer.Option("", "--confirm", help='Type: "SEND <count> <batch-id>"'),
) -> None:
    """Apply planned writes via the gateway (real client is gated by the rollout runbook)."""
    from spindle_gtm.apollo_gateway import GatewayError, RealApolloClient, execute_outbound
    from spindle_gtm.db import session_scope

    with session_scope() as session:
        b, manifests = _load_batch_and_manifests(batch)(session)
        if not confirm:
            report = execute_outbound(session, b, manifests, RealApolloClient(), dry_run=True)
            typer.echo(
                f"[dry-run] {len(manifests)} write(s); {report.skipped_duplicates} already "
                "applied. Pass --confirm to execute."
            )
            return
        try:
            report = execute_outbound(
                session, b, manifests, RealApolloClient(), dry_run=False, typed_confirm=confirm
            )
        except (GatewayError, NotImplementedError) as exc:
            typer.secho(str(exc), fg=typer.colors.RED)
            raise typer.Exit(code=1) from None
        session.commit()
        typer.echo(
            f"applied={report.applied} skipped={report.skipped_duplicates} failed={report.failed}"
        )


@outbound_app.command("cancel")
def outbound_cancel(batch: int = typer.Option(..., "--batch")) -> None:
    """Cancel the batch and all not-yet-applied manifests."""
    from spindle_gtm.apollo_gateway import cancel_outbound
    from spindle_gtm.db import session_scope

    with session_scope() as session:
        b, manifests = _load_batch_and_manifests(batch)(session)
        n = cancel_outbound(session, b, manifests)
        session.commit()
        typer.echo(f"cancelled batch {batch} ({n} pending manifest(s))")


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
