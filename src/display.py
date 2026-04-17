"""Rich terminal output — panels, colors, spinners, tables for demo display."""

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()


class DemoDisplay:
    """Video-ready terminal output using Rich."""

    def intro_banner(self) -> None:
        banner = Text()
        banner.append("Preflight x TRON\n", style="bold white")
        banner.append("Treasury Guardian Demo\n\n", style="bold cyan")
        banner.append("Three-solver consensus verification + ZK proof receipts\n", style="dim")
        banner.append("before any USDT moves on-chain (Nile testnet)", style="dim")
        console.print(Panel(banner, border_style="bright_cyan", box=box.DOUBLE))
        console.print()

    def scenario_header(self, number: int, name: str, description: str) -> None:
        console.print()
        console.rule(f"[bold yellow]Scenario {number}: {name}[/bold yellow]")
        console.print(f"  [dim]{description}[/dim]")
        console.print()

    def agent_thinking(self, message: str) -> None:
        console.print(
            Panel(
                f"[bold]Agent intent:[/bold]\n{message}",
                title="[blue]Agent Decision[/blue]",
                border_style="blue",
            )
        )

    def preflight_screening(self, result: dict) -> None:
        should_check = result.get("should_check", result.get("relevance", False))
        matched = result.get("matched_variables", result.get("matched", []))
        status = "[green]RELEVANT[/green]" if should_check else "[yellow]SKIPPED[/yellow]"

        content = f"Status: {status}\n"
        if matched:
            content += f"Matched variables: {matched}\n"
        time_ms = result.get("time_ms", result.get("duration_ms", "?"))
        content += f"Screening time: {time_ms}ms"

        console.print(
            Panel(
                content,
                title="[yellow]Preflight Relevance Screening (free)[/yellow]",
                border_style="yellow",
            )
        )

    def solver_consensus(self, result: dict) -> None:
        verdict = result.get("result", "UNKNOWN")
        is_sat = verdict == "SAT"
        color = "green" if is_sat else "red"
        icon = "APPROVED" if is_sat else "BLOCKED"

        content = f"[bold {color}]Verdict: {verdict} ({icon})[/bold {color}]\n\n"

        # Show individual solver results if available
        for key in ("llm_result", "ar_result", "z3_result"):
            if key in result:
                label = key.replace("_result", "").upper()
                val = result[key]
                val_color = "green" if val == "SAT" else "red" if val == "UNSAT" else "yellow"
                content += f"  {label}: [{val_color}]{val}[/{val_color}]\n"

        detail = result.get("detail", "")
        if detail:
            content += f"\n[dim]Detail: {detail}[/dim]\n"

        time_ms = result.get("verification_time_ms", result.get("duration_ms", "?"))
        content += f"\nVerification time: {time_ms}ms"

        console.print(
            Panel(
                content,
                title=f"[{color}]3-Solver Consensus Check ($0.01)[/{color}]",
                border_style=color,
            )
        )

    def settlement_result(self, tx_result: dict) -> None:
        tx_hash = tx_result.get("tx_hash", "N/A")
        network = tx_result.get("network", "tron:nile")
        body = tx_result.get("body", {})

        content = "[bold green]Payment settled on-chain[/bold green]\n\n"
        content += f"Network:  {network}\n"
        content += f"TX hash:  {tx_hash}\n"
        if body:
            content += f"\nAPI response: {body}"

        console.print(
            Panel(
                content,
                title="[green]x402 Settlement[/green]",
                border_style="green",
            )
        )

    def settlement_fallback(self, tx_hash: str, amount: float, recipient: str) -> None:
        content = "[bold green]Direct TRC-20 transfer completed[/bold green]\n\n"
        content += f"Amount:    {amount} USDT\n"
        content += f"Recipient: {recipient}\n"
        content += f"TX hash:   {tx_hash}\n"
        content += "Network:   tron:nile"

        console.print(
            Panel(
                content,
                title="[green]Fallback Settlement (direct transfer)[/green]",
                border_style="green",
            )
        )

    def blocked_result(self, detail: str, proof_id: str | None = None) -> None:
        content = "[bold red]Payment BLOCKED by Preflight[/bold red]\n\n"
        content += f"Reason: {detail}\n"
        if proof_id:
            content += f"Proof ID: {proof_id}"

        console.print(
            Panel(
                content,
                title="[red]Transaction Blocked[/red]",
                border_style="red",
            )
        )

    def proof_receipt(self, proof: dict) -> None:
        if not proof or proof.get("error"):
            console.print(
                Panel(
                    f"[yellow]Proof not available: {proof.get('error', 'unknown')}[/yellow]",
                    title="[cyan]ZK Proof Receipt[/cyan]",
                    border_style="cyan",
                )
            )
            return

        content = ""
        for key in ("proof_id", "policy_hash", "result", "valid", "trace_length", "created_at"):
            if key in proof:
                content += f"{key}: {proof[key]}\n"

        console.print(
            Panel(
                content.rstrip(),
                title="[cyan]ZK Proof Receipt[/cyan]",
                border_style="cyan",
            )
        )

    def proof_verification(self, result: dict) -> None:
        valid = result.get("valid", False)
        color = "green" if valid else "red"

        content = f"[bold {color}]Valid: {valid}[/bold {color}]\n"
        for key in ("policy_hash", "claimed_result", "verify_ms"):
            if key in result:
                content += f"{key}: {result[key]}\n"

        console.print(
            Panel(
                content.rstrip(),
                title="[cyan]Proof Verification[/cyan]",
                border_style="cyan",
            )
        )

    def balance_check(self, before: float, after: float) -> None:
        diff = after - before
        color = "red" if diff < 0 else "green" if diff > 0 else "dim"
        console.print(
            f"  Balance: {before:.4f} USDT -> {after:.4f} USDT ([{color}]{diff:+.4f}[/{color}])"
        )

    def skipped(self, reason: str) -> None:
        console.print(f"  [dim]Skipped: {reason}[/dim]")

    def info(self, message: str) -> None:
        console.print(f"  [dim]{message}[/dim]")

    def error(self, message: str) -> None:
        console.print(f"  [bold red]Error: {message}[/bold red]")

    def summary_table(self, results: list[dict]) -> None:
        console.print()
        console.rule("[bold cyan]Summary[/bold cyan]")
        console.print()

        table = Table(box=box.ROUNDED, show_header=True, header_style="bold")
        table.add_column("#", style="dim", width=3)
        table.add_column("Scenario", min_width=25)
        table.add_column("Verdict", width=10)
        table.add_column("Proof ID", min_width=12)

        for r in results:
            actual = r.get("actual", "?")
            verdict_styled = (
                f"[green]{actual}[/green]"
                if actual == "SAT"
                else f"[red]{actual}[/red]"
            )
            proof = r.get("proof_id", "-") or "-"
            table.add_row(
                str(r.get("number", "?")),
                r.get("name", "?"),
                verdict_styled,
                str(proof)[:20],
            )

        console.print(table)
        console.print()
