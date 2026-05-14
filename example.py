#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "rich",
# ]
# ///

"""
Floating-Point Precision Demo

Zeigt, wie 0.1 + 0.1 + ... (10x) NICHT exakt 1.0 ergibt,
und die while-Schleife deshalb unendlich läuft.

Usage:
    uv run float_demo.py
"""

import os
import sys
from datetime import datetime, timedelta

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc


# ═══════════════════════════════════════════════════════════════════════════
# UV Bootstrap (same pattern as train.py)
# ═══════════════════════════════════════════════════════════════════════════

def compute_exclude_newer_date(days_back=8):
    return (datetime.now(UTC) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

def should_set_exclude_newer():
    return not os.environ.get("UV_EXCLUDE_NEWER")

def restart_with_uv(script_path, args, env):
    try:
        os.execvpe("uv", ["uv", "run", "--quiet", script_path] + args, env)
    except FileNotFoundError:
        print("uv is not installed. Try:")
        print("curl -LsSf https://astral.sh/uv/install.sh | sh")
        sys.exit(1)

def ensure_safe_env():
    if not should_set_exclude_newer():
        return
    past_date = compute_exclude_newer_date(8)
    os.environ["UV_EXCLUDE_NEWER"] = past_date
    restart_with_uv(sys.argv[0], sys.argv[1:], os.environ)

ensure_safe_env()

# ═══════════════════════════════════════════════════════════════════════════
# Imports (after uv bootstrap)
# ═══════════════════════════════════════════════════════════════════════════

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()

# ═══════════════════════════════════════════════════════════════════════════
# Demo
# ═══════════════════════════════════════════════════════════════════════════

def main():
    console.print(Panel(
        "[bold white]Floating-Point Precision Problem[/]\n"
        "[dim]Warum 0.1 + 0.1 + ... ≠ 1.0[/]",
        border_style="bold cyan",
        padding=(1, 4),
    ))

    # ── Section 1: Was ist 0.1 wirklich? ────────────────────────────────
    console.print("\n[bold cyan]═══ Was ist 0.1 wirklich? ═══[/]\n")

    table = Table(box=box.ROUNDED, show_lines=True, title="Float-Repräsentation")
    table.add_column("Ausdruck", style="bold white")
    table.add_column("print()", style="green")
    table.add_column("Tatsächlicher Wert (20 Stellen)", style="yellow")
    table.add_column("Exakt?", style="bold")

    cases = [
        ("0.1", 0.1),
        ("0.2", 0.2),
        ("0.1 + 0.1 + 0.1", 0.1 + 0.1 + 0.1),
        ("0.3", 0.3),
        ("10 * 0.1", 10 * 0.1),
        ("sum([0.1]*10)", sum([0.1] * 10)),
    ]

    for label, val in cases:
        printed = str(val)
        precise = f"{val:.20f}"
        is_exact = precise.rstrip('0').endswith('.0') or val == int(val) if '.' in precise else True
        marker = "[green]✓[/]" if is_exact else "[red]✗[/]"
        table.add_row(label, printed, precise, marker)

    console.print(table)

    # ── Section 2: Das Problem demonstrieren ────────────────────────────
    console.print("\n[bold cyan]═══ Die Endlosschleife ═══[/]\n")

    console.print("[white]Code:[/]")
    console.print(Panel(
        "[green]x = 0.0\n"
        "while x != 1.0:\n"
        "    x += 0.1[/]",
        title="[bold red]⚠ ENDLOSSCHLEIFE",
        border_style="red",
    ))

    console.print("\n[white]Simulation (mit Sicherheits-Abbruch nach 15 Iterationen):[/]\n")

    x = 0.0
    step = 0.1
    target = 1.0
    max_iter = 15

    iter_table = Table(box=box.SIMPLE, show_header=True)
    iter_table.add_column("Iter", style="dim", justify="right")
    iter_table.add_column("x (print)", style="green")
    iter_table.add_column("x (wirklich)", style="yellow")
    iter_table.add_column("x == 1.0?", style="bold")
    iter_table.add_column("Differenz zu 1.0", style="magenta")

    for i in range(1, max_iter + 1):
        x += step
        printed = f"{x}"
        precise = f"{x:.20f}"
        is_one = x == target
        diff = x - target

        if is_one:
            marker = "[bold green]TRUE ✓[/]"
        elif abs(diff) < 1e-10:
            marker = "[bold yellow]FAST! (aber nein)[/]"
        else:
            marker = "[red]FALSE[/]"

        diff_str = f"{diff:+.20e}"

        # Highlight the critical iterations
        if i == 10:
            iter_table.add_row(
                f"[bold red]{i}[/]",
                f"[bold red]{printed}[/]",
                f"[bold red]{precise}[/]",
                marker,
                f"[bold red]{diff_str}[/]",
            )
        elif i == 11:
            iter_table.add_row(
                f"[bold yellow]{i}[/]",
                f"[bold yellow]{printed}[/]",
                f"[bold yellow]{precise}[/]",
                marker,
                f"[bold yellow]{diff_str}[/]",
            )
        else:
            iter_table.add_row(str(i), printed, precise, marker, diff_str)

    console.print(iter_table)

    # ── Section 3: Erklärung ────────────────────────────────────────────
    console.print("\n[bold cyan]═══ Was passiert hier? ═══[/]\n")

    x_at_10 = sum([0.1] * 10)
    x_at_11 = sum([0.1] * 11)

    explanation = Table(box=box.ROUNDED, show_lines=True)
    explanation.add_column("Schritt", style="bold")
    explanation.add_column("Erklärung", style="white")

    explanation.add_row(
        "[yellow]Iteration 10[/]",
        f"x = [bold yellow]{x_at_10:.20f}[/]\n"
        f"Das ist [bold red]0.99999999999999988898[/] — knapp UNTER 1.0!\n"
        f"[dim]print() zeigt '{x_at_10}' weil Python auf 17 Stellen rundet.[/]"
    )
    explanation.add_row(
        "[yellow]Iteration 11[/]",
        f"x = [bold yellow]{x_at_11:.20f}[/]\n"
        f"x ist jetzt ÜBER 1.0 — es hat 1.0 [bold red]übersprungen[/]!\n"
        f"Die Schleife trifft 1.0 [bold red]NIE EXAKT[/] → ∞ Loop"
    )
    explanation.add_row(
        "[green]Warum?[/]",
        "[white]0.1₁₀ = 0.0001100110011...₂ (unendliche Periode in Binär)\n"
        "Jede Addition akkumuliert einen winzigen Rundungsfehler.\n"
        "Nach 10 Additionen: Fehler ≈ -1.11e-16 (unter 1.0)\n"
        "→ x springt von 0.999...9 direkt auf 1.099...9[/]"
    )

    console.print(explanation)

    # ── Section 4: print() lügt! ───────────────────────────────────────
    console.print("\n[bold cyan]═══ print() lügt! ═══[/]\n")

    lie_table = Table(box=box.ROUNDED, title="[bold red]Die Lüge von print()")
    lie_table.add_column("Ausdruck", style="white")
    lie_table.add_column("print() sagt", style="green")
    lie_table.add_column("Wahrheit", style="red")
    lie_table.add_column("== 1.0?", style="bold")

    val = 0.1 + 0.1 + 0.1 + 0.1 + 0.1 + 0.1 + 0.1 + 0.1 + 0.1 + 0.1
    lie_table.add_row(
        "0.1+0.1+...+0.1 (10x)",
        f"{val}",
        f"{val:.20f}",
        "[bold red]False[/]" if val != 1.0 else "[bold green]True[/]",
    )

    val2 = 1/3 + 1/3 + 1/3
    lie_table.add_row(
        "1/3 + 1/3 + 1/3",
        f"{val2}",
        f"{val2:.20f}",
        "[bold green]True[/]" if val2 == 1.0 else "[bold red]False[/]",
    )

    val3 = 0.1 + 0.2
    lie_table.add_row(
        "0.1 + 0.2",
        f"{val3}",
        f"{val3:.20f}",
        "[bold red]False[/]" if val3 != 0.3 else "[bold green]True[/]",
    )

    console.print(lie_table)

    # ── Section 5: Die Lösung ───────────────────────────────────────────
    console.print("\n[bold cyan]═══ Die Lösung ═══[/]\n")

    import math
    from fractions import Fraction

    solution_table = Table(box=box.ROUNDED, show_lines=True,
                           title="[bold green]Korrekte Vergleiche")
    solution_table.add_column("Methode", style="bold cyan")
    solution_table.add_column("Code", style="green")
    solution_table.add_column("Ergebnis", style="bold")

    x_broken = sum([0.1] * 10)

    solution_table.add_row(
        "[red]FALSCH[/]",
        "x == 1.0",
        f"[bold red]{x_broken == 1.0}[/]",
    )
    solution_table.add_row(
        "[green]math.isclose()[/]",
        "math.isclose(x, 1.0)",
        f"[bold green]{math.isclose(x_broken, 1.0)}[/]",
    )
    solution_table.add_row(
        "[green]Epsilon[/]",
        "abs(x - 1.0) < 1e-9",
        f"[bold green]{abs(x_broken - 1.0) < 1e-9}[/]",
    )
    solution_table.add_row(
        "[green]fractions[/]",
        "Fraction(1,10) * 10 == 1",
        f"[bold green]{Fraction(1, 10) * 10 == 1}[/]",
    )
    solution_table.add_row(
        "[green]Integer-Trick[/]",
        "int(x * 10) == 10",
        f"[bold green]{round(x_broken * 10) == 10}[/]",
    )

    console.print(solution_table)

    # ── Section 6: Korrigierte Schleife ─────────────────────────────────
    console.print("\n[bold cyan]═══ Korrigierte Schleife ═══[/]\n")

    console.print(Panel(
        "[green]import math\n\n"
        "x = 0.0\n"
        "iterations = 0\n\n"
        "while not math.isclose(x, 1.0, rel_tol=1e-9):\n"
        "    x += 0.1\n"
        "    iterations += 1\n\n"
        "print(f'Fertig nach {iterations} Iterationen')[/]",
        title="[bold green]✓ KORREKT",
        border_style="green",
    ))

    # Actually run it
    x = 0.0
    iterations = 0
    while not math.isclose(x, 1.0, rel_tol=1e-9):
        x += 0.1
        iterations += 1
        if iterations > 100:
            break

    console.print(
        f"  [bold green]→ Fertig nach {iterations} Iterationen[/] "
        f"[dim](x = {x:.20f})[/]\n"
    )

    # ── Final summary ───────────────────────────────────────────────────
    console.print(Panel(
        "[bold white]Merke:[/]\n\n"
        "  [bold red]✗[/] Niemals [bold]== / !=[/] mit Floats verwenden\n"
        "  [bold green]✓[/] Immer [bold]math.isclose()[/] oder Epsilon-Vergleich\n"
        "  [bold green]✓[/] Oder: [bold]fractions.Fraction[/] für exakte Brüche\n"
        "  [bold green]✓[/] Oder: Integer-Arithmetik (Cents statt Euro, etc.)\n\n"
        "  [dim]IEEE 754 double: 64 bit → ~15-17 signifikante Dezimalstellen\n"
        "  0.1₁₀ = 0.00011001100110011...₂ (unendliche Periode)[/]",
        title="[bold cyan]📝 Zusammenfassung",
        border_style="cyan",
        padding=(1, 2),
    ))


if __name__ == "__main__":
    main()
