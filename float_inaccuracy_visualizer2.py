#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "rich",
# ]
# ///

import os
import sys
from datetime import datetime, timedelta

try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc


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


# Must run BEFORE heavy imports
ensure_safe_env()

# ============================================================
# Now safe to import everything
# ============================================================

import math
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich import box
from rich.rule import Rule

console = Console()


class TrackedFloat:
    """
    A float wrapper using conservative interval arithmetic.
    The true mathematical result is guaranteed to lie within [lo, hi].
    """

    def __init__(self, value, lo=None, hi=None):
        if isinstance(value, TrackedFloat):
            self.value = value.value
            self.lo = value.lo
            self.hi = value.hi
            return

        self.value = float(value)

        if lo is not None and hi is not None:
            self.lo = lo
            self.hi = hi
        else:
            ulp = math.ulp(self.value) if self.value != 0 else 2**-1074
            self.lo = self.value - 0.5 * ulp
            self.hi = self.value + 0.5 * ulp

    @staticmethod
    def _widen(result):
        return math.ulp(abs(result)) if result != 0 else 2**-1074

    def __add__(self, other):
        other = other if isinstance(other, TrackedFloat) else TrackedFloat(other)
        value = self.value + other.value
        lo = self.lo + other.lo
        hi = self.hi + other.hi
        lo -= self._widen(lo)
        hi += self._widen(hi)
        return TrackedFloat(value, lo, hi)

    def __radd__(self, other):
        return TrackedFloat(other).__add__(self)

    def __sub__(self, other):
        other = other if isinstance(other, TrackedFloat) else TrackedFloat(other)
        value = self.value - other.value
        lo = self.lo - other.hi
        hi = self.hi - other.lo
        lo -= self._widen(lo)
        hi += self._widen(hi)
        return TrackedFloat(value, lo, hi)

    def __rsub__(self, other):
        return TrackedFloat(other).__sub__(self)

    def __mul__(self, other):
        other = other if isinstance(other, TrackedFloat) else TrackedFloat(other)
        value = self.value * other.value
        candidates = [
            self.lo * other.lo, self.lo * other.hi,
            self.hi * other.lo, self.hi * other.hi,
        ]
        lo = min(candidates)
        hi = max(candidates)
        lo -= self._widen(lo)
        hi += self._widen(hi)
        return TrackedFloat(value, lo, hi)

    def __rmul__(self, other):
        return TrackedFloat(other).__mul__(self)

    def __truediv__(self, other):
        other = other if isinstance(other, TrackedFloat) else TrackedFloat(other)
        value = self.value / other.value

        if other.lo <= 0 <= other.hi:
            return TrackedFloat(value, float('-inf'), float('inf'))

        candidates = [
            self.lo / other.lo, self.lo / other.hi,
            self.hi / other.lo, self.hi / other.hi,
        ]
        lo = min(candidates)
        hi = max(candidates)
        lo -= self._widen(lo)
        hi += self._widen(hi)
        return TrackedFloat(value, lo, hi)

    def __rtruediv__(self, other):
        return TrackedFloat(other).__truediv__(self)

    def __pow__(self, other):
        if isinstance(other, (int, float)) and not isinstance(other, TrackedFloat):
            exp = other
            value = self.value ** exp

            if isinstance(exp, int) or (isinstance(exp, float) and exp == int(exp)):
                exp_int = int(exp)
                if exp_int % 2 == 0 and exp_int > 0:
                    if self.lo >= 0:
                        lo, hi = self.lo ** exp, self.hi ** exp
                    elif self.hi <= 0:
                        lo, hi = self.hi ** exp, self.lo ** exp
                    else:
                        lo = 0.0
                        hi = max(self.lo ** exp, self.hi ** exp)
                else:
                    lo, hi = self.lo ** exp, self.hi ** exp
                    if lo > hi:
                        lo, hi = hi, lo
            else:
                candidates = []
                for base in [self.lo, self.hi]:
                    try:
                        candidates.append(base ** exp)
                    except (ValueError, ZeroDivisionError, OverflowError):
                        pass
                if not candidates:
                    return TrackedFloat(value, float('-inf'), float('inf'))
                lo, hi = min(candidates), max(candidates)

            lo -= self._widen(lo)
            hi += self._widen(hi)
            return TrackedFloat(value, lo, hi)
        else:
            other = other if isinstance(other, TrackedFloat) else TrackedFloat(other)
            value = self.value ** other.value
            candidates = []
            for base in [self.lo, self.hi]:
                for exp in [other.lo, other.hi]:
                    try:
                        candidates.append(base ** exp)
                    except (ValueError, ZeroDivisionError, OverflowError):
                        pass
            if not candidates:
                return TrackedFloat(value, float('-inf'), float('inf'))
            lo = min(candidates) - self._widen(min(candidates))
            hi = max(candidates) + self._widen(max(candidates))
            return TrackedFloat(value, lo, hi)

    def __neg__(self):
        return TrackedFloat(-self.value, -self.hi, -self.lo)

    def __abs__(self):
        value = abs(self.value)
        if self.lo >= 0:
            return TrackedFloat(value, self.lo, self.hi)
        elif self.hi <= 0:
            return TrackedFloat(value, -self.hi, -self.lo)
        else:
            return TrackedFloat(value, 0.0, max(-self.lo, self.hi))

    def sqrt(self):
        value = math.sqrt(self.value)
        lo_in = max(self.lo, 0.0)
        lo = math.sqrt(lo_in)
        hi = math.sqrt(self.hi)
        lo -= self._widen(lo)
        hi += self._widen(hi)
        return TrackedFloat(value, lo, hi)

    @property
    def uncertainty(self):
        return self.hi - self.lo

    @property
    def relative_uncertainty(self):
        if self.value == 0:
            return float('inf')
        return self.uncertainty / abs(self.value)

    @property
    def accurate_digits(self):
        if self.value == 0 or self.uncertainty <= 0:
            return 15
        ratio = abs(self.value) / self.uncertainty
        if ratio <= 1:
            return 0
        return max(0, int(math.log10(ratio)))

    def __float__(self):
        return self.value

    def __repr__(self):
        return f"TrackedFloat({self.value}, [{self.lo}, {self.hi}])"


# ============================================================
# ENHANCED VISUALIZATION HELPERS
# ============================================================

GRADIENT_COLORS = [
    "#ff0000", "#ff2200", "#ff4400", "#ff6600", "#ff8800",
    "#ffaa00", "#ffcc00", "#ffee00", "#ddff00", "#bbff00",
    "#88ff00", "#66ff00", "#44ff00", "#22ff00", "#00ff00",
    "#00ff88",
]


def get_gradient_color(digits):
    idx = max(0, min(15, digits))
    return GRADIENT_COLORS[idx]


def make_precision_bar(digits, width=40):
    """Create a fancy gradient precision bar with decay visualization."""
    max_d = 15
    filled = int((digits / max_d) * width)
    filled = max(0, min(width, filled))
    empty = width - filled

    bar_text = Text()
    for i in range(filled):
        if i < filled * 0.3:
            bar_text.append("█", style=f"bold {GRADIENT_COLORS[14]}")
        elif i < filled * 0.6:
            bar_text.append("█", style=f"bold {GRADIENT_COLORS[11]}")
        elif i < filled * 0.85:
            bar_text.append("▓", style=f"{GRADIENT_COLORS[7]}")
        else:
            bar_text.append("▒", style=f"{GRADIENT_COLORS[4]}")

    for i in range(min(3, empty)):
        bar_text.append("░", style="dim red")
    for i in range(max(0, empty - 3)):
        bar_text.append("·", style="dim #333333")

    return bar_text


def make_explosion_meter(digits):
    """Visual 'danger meter' showing how close to total failure."""
    icons = ["💥", "☠️", "🌋", "💀", "🔴", "🔴", "🟠", "🟠", "🟡", "🟡", "🟢", "🟢", "🟢", "🟢", "🟢", "🟢"]
    return icons[min(digits, 15)]


def make_interval_visual(tf, width=50):
    """
    Create a visual representation of where the value sits within its interval.
    Shows the interval as a line with the value marked.
    """
    if tf.uncertainty <= 0 or math.isinf(tf.lo) or math.isinf(tf.hi):
        if math.isinf(tf.uncertainty):
            return Text("◄" + "?" * (width - 2) + "►", style="bold red")
        return Text("─" * width, style="dim green")

    if tf.hi == tf.lo:
        pos = width // 2
    else:
        pos = int(((tf.value - tf.lo) / (tf.hi - tf.lo)) * (width - 1))
        pos = max(0, min(width - 1, pos))

    result = Text()
    color = get_gradient_color(tf.accurate_digits)

    result.append("◄", style=f"bold {color}")
    for i in range(1, width - 1):
        if i == pos:
            result.append("●", style="bold white")
        elif abs(i - pos) <= 1:
            result.append("─", style=f"bold {color}")
        else:
            result.append("─", style=f"dim {color}")
    result.append("►", style=f"bold {color}")

    return result


def make_digit_display(tf):
    """
    Show the value with reliable digits in green and unreliable in red.
    """
    digits = tf.accurate_digits
    val_str = f"{tf.value:.15g}"

    result = Text()
    sig_count = 0
    in_number = False
    for i, ch in enumerate(val_str):
        if ch in '0123456789':
            if ch != '0' or in_number:
                in_number = True
                sig_count += 1
            elif not in_number and ch == '0' and i > 0 and val_str[i-1] == '.':
                pass
            if sig_count <= digits:
                result.append(ch, style="bold bright_green")
            else:
                result.append(ch, style="bold red")
        elif ch == 'e' or ch == 'E':
            result.append(val_str[i:], style="dim")
            break
        else:
            result.append(ch, style="dim white")

    return result


def format_enhanced_row(label, tf, expected=None):
    """Format a TrackedFloat as an enhanced rich table row."""
    digits = tf.accurate_digits
    color = get_gradient_color(digits)
    meter = make_explosion_meter(digits)
    bar = make_precision_bar(digits)
    digit_display = make_digit_display(tf)

    unc_str = f"±{tf.uncertainty / 2:.2e}" if not math.isinf(tf.uncertainty) else "±∞"

    row = [
        label,
        digit_display,
        make_interval_visual(tf),
        Text(unc_str, style=f"{color}"),
        Text(f"{digits}", style=f"bold {color}"),
        meter,
        bar,
    ]
    if expected is not None:
        row.append(Text(str(expected), style="bright_yellow"))
    return row


def make_enhanced_table(title, rows, show_expected=False, subtitle=None):
    """Build an enhanced Rich table."""
    full_title = f"\n{title}"
    if subtitle:
        full_title += f"\n[dim italic]{subtitle}[/dim italic]"

    table = Table(
        title=full_title,
        box=box.HEAVY_EDGE,
        title_style="bold bright_cyan",
        header_style="bold white on #1a1a2e",
        show_lines=True,
        padding=(0, 1),
        border_style="bright_blue",
    )
    table.add_column("Step", style="bold bright_white", min_width=18)
    table.add_column("Value [green]reliable[/] [red]noise[/]", min_width=24)
    table.add_column("Interval ◄──●──►", min_width=52, justify="center")
    table.add_column("± Error", min_width=12, justify="right")
    table.add_column("Dig", justify="center", min_width=4)
    table.add_column("⚠", justify="center", min_width=3)
    table.add_column("Precision Remaining", min_width=42)
    if show_expected:
        table.add_column("Expected", style="bright_yellow", min_width=12)

    for row in rows:
        table.add_row(*row)

    return table


def print_section_header(emoji, title, description):
    """Print a dramatic section header."""
    console.print()
    console.print(Rule(style="bright_blue"))
    console.print()
    header = Text()
    header.append(f"  {emoji} ", style="bold")
    header.append(title, style="bold bright_cyan underline")
    console.print(header)
    console.print(f"  [dim italic]{description}[/]")
    console.print()


def print_result_box(lines, style="yellow"):
    """Print a result summary in a colored box."""
    content = "\n".join(lines)
    console.print(Panel(
        content,
        border_style=style,
        padding=(0, 2),
        title="[bold]Result[/]",
    ))


# ============================================================
# DEMOS
# ============================================================

def demo_repeated_addition():
    print_section_header(
        "🔢", "REPEATED ADDITION OF 0.1",
        "0.1 cannot be exactly represented in binary. Watch error accumulate with each addition."
    )

    rows = []
    total = TrackedFloat(0.1)
    rows.append(format_enhanced_row("0.1 × 1", total, "0.1"))
    for i in range(2, 31):
        total = total + TrackedFloat(0.1)
        expected = round(i * 0.1, 10)
        if i <= 10 or i % 5 == 0:
            rows.append(format_enhanced_row(f"0.1 × {i}", total, str(expected)))

    table = make_enhanced_table(
        "Summing 0.1 → should reach 3.0 at ×30",
        rows, show_expected=True,
        subtitle="Each addition of 0.1 introduces ~0.5 ULP of rounding error"
    )
    console.print(table)

    print_result_box([
        f"[bold]True answer:[/] 3.0",
        f"[bold]Float answer:[/] {float(total):.17g}",
        f"[bold]Uncertainty:[/] [red]±{total.uncertainty / 2:.2e}[/]",
        f"[bold]Digits lost:[/] [red]{15 - total.accurate_digits}[/] out of 15",
    ])


def demo_catastrophic_cancellation():
    print_section_header(
        "💥", "CATASTROPHIC CANCELLATION",
        "Subtracting nearly-equal numbers destroys significant digits. This is the #1 source of numerical bugs!"
    )

    rows = []
    epsilons = [1e-3, 1e-5, 1e-7, 1e-8, 1e-9, 1e-10, 1e-11, 1e-12, 1e-13, 1e-14, 1e-15]
    for eps in epsilons:
        a = TrackedFloat(1.0) + TrackedFloat(eps)
        b = a - TrackedFloat(1.0)
        label = f"(1+{eps:.0e})-1"
        rows.append(format_enhanced_row(label, b, f"{eps:.0e}"))

    table = make_enhanced_table(
        "Catastrophic Cancellation: (1 + ε) - 1 for decreasing ε",
        rows, show_expected=True,
        subtitle="Watch the precision bar collapse as ε approaches machine epsilon!"
    )
    console.print(table)

    print_result_box([
        "[bold red]⚠ DANGER:[/] When ε ≈ machine epsilon (~1e-16),",
        "  the subtraction produces [bold red]ZERO reliable digits![/]",
        "",
        "[dim]This is why numerical algorithms avoid subtracting",
        "nearly-equal quantities whenever possible.[/]",
    ], style="red")


def demo_multiplication_chain():
    print_section_header(
        "📈", "MULTIPLICATION ERROR GROWTH",
        "Multiplying by 1.0001 ten thousand times. Each multiply adds ~0.5 ULP relative error."
    )

    rows = []
    x = TrackedFloat(1.0)
    factor = TrackedFloat(1.0001)
    milestones = {1, 5, 10, 25, 50, 100, 250, 500, 1000, 2000, 5000, 10000}

    for i in range(1, 10001):
        x = x * factor
        if i in milestones:
            rows.append(format_enhanced_row(f"× 1.0001^{i}", x))

    table = make_enhanced_table(
        "Multiplying by 1.0001 in a loop (10,000 iterations)",
        rows,
        subtitle="Relative error grows roughly as O(√n) for multiplication chains"
    )
    console.print(table)

    print_result_box([
        f"[bold]After 10,000 multiplications:[/]",
        f"  Value ≈ e ≈ {float(x):.10f}",
        f"  Uncertainty: [red]±{x.uncertainty / 2:.2e}[/]",
        f"  Reliable digits: [bold]{x.accurate_digits}[/] / 15",
        f"  Digits lost: [red]{15 - x.accurate_digits}[/]",
    ])


def demo_division_roundtrip():
    print_section_header(
        "🔄", "DIVISION ROUND-TRIP",
        "Divide by 7 sixty times, then multiply back. Can we recover the original value?"
    )

    rows = []
    val = TrackedFloat(1.0)
    rows.append(format_enhanced_row("Start", val, "1.0"))

    n_trips = 60
    for i in range(1, n_trips + 1):
        val = val / TrackedFloat(7.0)
        if i in [1, 5, 10, 20, 30, 40, 50, 60]:
            rows.append(format_enhanced_row(f"÷7 ×{i}", val))

    for i in range(1, n_trips + 1):
        val = val * TrackedFloat(7.0)
        if i in [1, 10, 20, 30, 40, 50, 60]:
            exp = "1.0" if i == n_trips else ""
            rows.append(format_enhanced_row(f"×7 ×{i} (back)", val, exp))

    table = make_enhanced_table(
        f"Divide by 7 × {n_trips}, then multiply back × {n_trips}",
        rows, show_expected=True,
        subtitle="120 total operations — precision never fully recovers!"
    )
    console.print(table)

    print_result_box([
        f"[bold]Expected:[/] 1.0",
        f"[bold]Got:[/] {float(val):.17g}",
        f"[bold]Uncertainty:[/] [red]±{val.uncertainty / 2:.2e}[/]",
        f"[bold]Reliable digits:[/] {val.accurate_digits} / 15",
        "[dim]Precision lost in division is NOT recovered by multiplication![/]",
    ])


def demo_quadratic():
    print_section_header(
        "📐", "QUADRATIC FORMULA — CANCELLATION DISASTER",
        "Solving x² - 1000000.001x + 1 = 0. The small root suffers massive cancellation."
    )

    rows = []
    a = TrackedFloat(1.0)
    b = TrackedFloat(-1000000.001)
    c = TrackedFloat(1.0)

    b2 = b ** 2
    rows.append(format_enhanced_row("b²", b2))
    four_ac = TrackedFloat(4.0) * a * c
    rows.append(format_enhanced_row("4ac", four_ac))
    disc = b2 - four_ac
    rows.append(format_enhanced_row("b² - 4ac", disc))
    sq = disc.sqrt()
    rows.append(format_enhanced_row("√(b²-4ac)", sq))

    x1 = (-b + sq) / (TrackedFloat(2.0) * a)
    x2 = (-b - sq) / (TrackedFloat(2.0) * a)
    rows.append(format_enhanced_row("x₁ (large root)", x1))
    rows.append(format_enhanced_row("x₂ (small root)", x2))

    # Show the better way
    x2_better = c / (a * x1)
    rows.append(format_enhanced_row("x₂ via c/(a·x₁)", x2_better))

    table = make_enhanced_table(
        "Quadratic: x² - 1000000.001x + 1 = 0",
        rows,
        subtitle="The naive formula catastrophically cancels for the small root!"
    )
    console.print(table)

    print_result_box([
        f"[bold red]Naive x₂:[/] {float(x2):.17g}  ({x2.accurate_digits} digits)",
        f"[bold green]Better x₂ = c/(a·x₁):[/] {float(x2_better):.17g}  ({x2_better.accurate_digits} digits)",
        "",
        "[dim]Lesson: Use the identity x₂ = c/(a·x₁) to avoid cancellation![/]",
    ], style="green")


def demo_massive_sum():
    print_section_header(
        "🏔️", "MASSIVE SUMMATION — 100,000 ADDITIONS",
        "Adding 0.001 one hundred thousand times. Should equal 100.0 exactly."
    )

    rows = []
    total = TrackedFloat(0.0)
    milestones = {1, 10, 100, 500, 1000, 2500, 5000, 10000, 25000, 50000, 75000, 100000}

    for i in range(1, 100001):
        total = total + TrackedFloat(0.001)
        if i in milestones:
            expected = f"{i * 0.001:.3f}"
            rows.append(format_enhanced_row(f"+0.001 ×{i:>6d}", total, expected))

    table = make_enhanced_table(
        "Summing 0.001 × 100,000 → should reach 100.0",
        rows, show_expected=True,
        subtitle="Error grows as O(n) for naive summation — use math.fsum() instead!"
    )
    console.print(table)

    print_result_box([
        f"[bold]Expected:[/] 100.0",
        f"[bold]Got:[/] {float(total):.17g}",
        f"[bold]Off by:[/] [red]{abs(float(total) - 100.0):.2e}[/]",
        f"[bold]Uncertainty:[/] [red]±{total.uncertainty / 2:.2e}[/]",
        f"[bold]Digits lost:[/] [red]{15 - total.accurate_digits}[/] out of 15",
        "",
        "[bold cyan]Fix:[/] Use [bold]math.fsum()[/] for O(1) error instead of O(n)!",
    ])


def demo_sqrt_roundtrip():
    print_section_header(
        "🌀", "SQRT ROUND-TRIP — TOTAL PRECISION COLLAPSE",
        "Take √2 fifty times, then square back fifty times. Should return to 2.0..."
    )

    rows = []
    val = TrackedFloat(2.0)
    rows.append(format_enhanced_row("Start", val, "2.0"))

    for i in range(1, 51):
        val = val.sqrt()
        if i in [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]:
            rows.append(format_enhanced_row(f"√ ×{i}", val))

    for i in range(1, 51):
        val = val ** 2
        if i in [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]:
            exp = "2.0" if i == 50 else ""
            rows.append(format_enhanced_row(f"² ×{i} (back)", val, exp))

    table = make_enhanced_table(
        "√2 fifty times → ² fifty times (should return to 2.0)",
        rows, show_expected=True,
        subtitle="The value approaches 1.0 during sqrt phase, losing all information about '2'"
    )
    console.print(table)

    print_result_box([
        f"[bold]Expected:[/] 2.0",
        f"[bold]Got:[/] [bold red]{float(val):.17g}[/]",
        f"[bold]Uncertainty:[/] [bold red]±{val.uncertainty / 2:.2e}[/]",
        f"[bold]Reliable digits:[/] [bold red]{val.accurate_digits}[/] (ZERO!)",
        "",
        "[bold red]💀 TOTAL PRECISION COLLAPSE![/]",
        "[dim]After 50 sqrts, the value is so close to 1.0 that all",
        "information about the original '2' is lost in rounding noise.[/]",
    ], style="red")


def demo_harmonic_series():
    print_section_header(
        "📊", "HARMONIC SERIES",
        "H(n) = 1 + 1/2 + 1/3 + ... + 1/n. Each term requires a division AND an addition."
    )

    rows = []
    total = TrackedFloat(0.0)
    milestones = {1, 5, 10, 50, 100, 500, 1000, 2500, 5000, 10000, 25000, 50000}

    for i in range(1, 50001):
        total = total + TrackedFloat(1.0) / TrackedFloat(float(i))
        if i in milestones:
            rows.append(format_enhanced_row(f"H({i:>5d})", total))

    table = make_enhanced_table(
        "Harmonic Series H(n) = Σ 1/k for k=1..50,000",
        rows,
        subtitle="Two operations per term (÷ and +) means error grows faster than pure addition"
    )
    console.print(table)

    print_result_box([
        f"[bold]H(50000) ≈[/] {float(total):.15g}",
        f"[bold]Uncertainty:[/] [red]±{total.uncertainty / 2:.2e}[/]",
        f"[bold]Reliable digits:[/] {total.accurate_digits} / 15",
        "",
        "[dim]Note: Adding small terms (1/50000) to a large sum (~11)",
        "causes additional precision loss due to magnitude mismatch.[/]",
    ])


def demo_logistic_map():
    print_section_header(
        "🌪️", "CHAOTIC LOGISTIC MAP — ERROR EXPLOSION",
        "x(n+1) = 3.99 · x · (1-x). In the chaotic regime, errors grow EXPONENTIALLY."
    )

    rows = []
    r = TrackedFloat(3.99)
    x = TrackedFloat(0.5)
    rows.append(format_enhanced_row("x(0)", x))

    checkpoints = list(range(1, 6)) + list(range(6, 31, 2)) + list(range(35, 101, 5))
    checkpoint_set = set(checkpoints)

    for i in range(1, 101):
        x = r * x * (        TrackedFloat(1.0) - x)
        if i in checkpoint_set:
            rows.append(format_enhanced_row(f"x({i})", x))

    table = make_enhanced_table(
        "Logistic Map: x → 3.99·x·(1-x) starting from x(0) = 0.5",
        rows,
        subtitle="Chaos theory: Lyapunov exponent > 0 means errors double every ~1.5 iterations!"
    )
    console.print(table)

    print_result_box([
        "[bold red]🌋 TOTAL INFORMATION DESTRUCTION[/]",
        "",
        "The logistic map at r=3.99 is [bold]chaotic[/].",
        "The Lyapunov exponent λ ≈ ln(2) ≈ 0.69 means errors",
        "grow by a factor of ~2× every ~1.5 iterations.",
        "",
        "After ~50 iterations: [bold red]ZERO reliable digits.[/]",
        "The computed trajectory is [bold red]pure numerical fiction![/]",
        "",
        "[dim]This is why weather prediction beyond ~2 weeks is impossible —",
        "the atmosphere is a chaotic system with similar error amplification.[/]",
    ], style="red")


def demo_tower_of_operations():
    """Example 10: Mixed operations stress test."""
    print_section_header(
        "🗼", "TOWER OF MIXED OPERATIONS",
        "A gauntlet of +, -, ×, ÷, √, ² applied in sequence. Watch the error snowball!"
    )

    rows = []
    x = TrackedFloat(2.0)
    rows.append(format_enhanced_row("Start: 2.0", x))

    ops_log = []

    # Phase 1: Multiply and divide by π
    for i in range(10):
        x = x * TrackedFloat(3.14159)
        ops_log.append("×π")
    rows.append(format_enhanced_row("×π ×10", x))

    for i in range(10):
        x = x / TrackedFloat(3.14159)
        ops_log.append("÷π")
    rows.append(format_enhanced_row("÷π ×10 (back)", x, "2.0"))

    # Phase 2: Add and subtract tiny values
    for i in range(20):
        x = x + TrackedFloat(1e-10)
        ops_log.append("+1e-10")
    rows.append(format_enhanced_row("+1e-10 ×20", x))

    for i in range(20):
        x = x - TrackedFloat(1e-10)
        ops_log.append("-1e-10")
    rows.append(format_enhanced_row("-1e-10 ×20 (back)", x, "2.0"))

    # Phase 3: sqrt/square dance
    for i in range(15):
        x = x.sqrt()
        ops_log.append("√")
    rows.append(format_enhanced_row("√ ×15", x))

    for i in range(15):
        x = x ** 2
        ops_log.append("²")
    rows.append(format_enhanced_row("² ×15 (back)", x, "2.0"))

    # Phase 4: Multiply and divide by 1.01
    for i in range(50):
        x = x * TrackedFloat(1.01)
        ops_log.append("×1.01")
    rows.append(format_enhanced_row("×1.01 ×50", x))

    for i in range(50):
        x = x / TrackedFloat(1.01)
        ops_log.append("÷1.01")
    rows.append(format_enhanced_row("÷1.01 ×50 (back)", x, "2.0"))

    # Phase 5: Add and subtract 0.001
    for i in range(100):
        x = x + TrackedFloat(0.001)
        ops_log.append("+0.001")
    rows.append(format_enhanced_row("+0.001 ×100", x, "2.1"))

    for i in range(100):
        x = x - TrackedFloat(0.001)
        ops_log.append("-0.001")
    rows.append(format_enhanced_row("-0.001 ×100 (back)", x, "2.0"))

    table = make_enhanced_table(
        f"Tower of {len(ops_log)} Mixed Operations — all should return to 2.0",
        rows, show_expected=True,
        subtitle="×π ÷π +ε -ε √ ² ×1.01 ÷1.01 +0.001 -0.001 — a precision gauntlet!"
    )
    console.print(table)

    print_result_box([
        f"[bold]Total operations:[/] {len(ops_log)}",
        f"[bold]Expected final value:[/] 2.0",
        f"[bold]Actual value:[/] {float(x):.17g}",
        f"[bold]Uncertainty:[/] [red]±{x.uncertainty / 2:.2e}[/]",
        f"[bold]Reliable digits:[/] {x.accurate_digits} / 15",
        "",
        "[dim]Even though every operation was 'reversed', precision is permanently lost.[/]",
    ])


def demo_fibonacci_ratio():
    """Example 11: Computing the golden ratio via Fibonacci iteration."""
    print_section_header(
        "🐚", "FIBONACCI → GOLDEN RATIO",
        "Computing φ = lim(F(n+1)/F(n)) iteratively. Division of large numbers loses precision."
    )

    rows = []
    a = TrackedFloat(1.0)
    b = TrackedFloat(1.0)
    milestones = {1, 2, 3, 5, 10, 20, 30, 50, 75, 100, 150, 200}

    for i in range(1, 201):
        a, b = b, a + b
        if i in milestones:
            ratio = b / a
            rows.append(format_enhanced_row(f"F({i+1})/F({i})", ratio, "1.6180339887..."))

    ratio = b / a
    table = make_enhanced_table(
        "Golden Ratio via Fibonacci: φ = lim F(n+1)/F(n)",
        rows, show_expected=True,
        subtitle="As F(n) grows huge, both numerator and denominator lose absolute precision"
    )
    console.print(table)

    print_result_box([
        f"[bold]True φ =[/] 1.6180339887498948...",
        f"[bold]Computed:[/] {float(ratio):.17g}",
        f"[bold]Uncertainty:[/] [red]±{ratio.uncertainty / 2:.2e}[/]",
        f"[bold]Reliable digits:[/] {ratio.accurate_digits} / 15",
        "",
        "[dim]The ratio converges quickly, but the underlying F(n) values",
        "grow exponentially, accumulating error in the large numbers.[/]",
    ])


def demo_exp_taylor():
    """Example 12: Computing e^x via Taylor series."""
    print_section_header(
        "🧮", "TAYLOR SERIES FOR e^20",
        "e^x = Σ x^k/k!  — Large intermediate terms cancel to give a moderate result."
    )

    rows = []
    x_val = 20.0
    x = TrackedFloat(x_val)
    total = TrackedFloat(1.0)  # k=0 term
    term = TrackedFloat(1.0)
    rows.append(format_enhanced_row("k=0: 1", total))

    for k in range(1, 80):
        term = term * x / TrackedFloat(float(k))
        total = total + term
        if k in [1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 79]:
            term_val = float(term)
            if abs(term_val) > 0.001:
                label = f"k={k}: +{term_val:.4g}"
            else:
                label = f"k={k}: +tiny"
            rows.append(format_enhanced_row(label, total))

    true_val = math.exp(x_val)
    table = make_enhanced_table(
        f"Taylor Series: e^{x_val:.0f} = Σ {x_val:.0f}^k / k!  (80 terms)",
        rows,
        subtitle=f"True value: e^20 ≈ {true_val:.6e}. Intermediate terms reach ~4e7!"
    )
    console.print(table)

    print_result_box([
        f"[bold]True e^20 =[/] {true_val:.17g}",
        f"[bold]Computed:[/]   {float(total):.17g}",
        f"[bold]Abs error:[/]  [red]{abs(float(total) - true_val):.2e}[/]",
        f"[bold]Uncertainty:[/] [red]±{total.uncertainty / 2:.2e}[/]",
        f"[bold]Reliable digits:[/] {total.accurate_digits} / 15",
        "",
        "[dim]The Taylor series for e^x with large x has huge intermediate terms",
        "that mostly cancel — a recipe for precision loss![/]",
    ])


def demo_comparison_table():
    """Final summary: side-by-side comparison of all demos."""
    print_section_header(
        "📋", "FINAL SCOREBOARD",
        "How much precision did each scenario destroy?"
    )

    table = Table(
        title="\n🏆 Precision Destruction Leaderboard",
        box=box.DOUBLE_EDGE,
        title_style="bold bright_yellow",
        header_style="bold white on #2a0a3a",
        show_lines=True,
        border_style="bright_magenta",
        padding=(0, 1),
    )
    table.add_column("Scenario", style="bold", min_width=35)
    table.add_column("Operations", justify="right", min_width=12)
    table.add_column("Digits Lost", justify="center", min_width=12)
    table.add_column("Severity", min_width=42)
    table.add_column("Verdict", justify="center", min_width=8)

    scenarios = [
        ("0.1 × 30 additions", "30", 1, "Mild"),
        ("(1+ε)-1 cancellation (ε=1e-15)", "2", 15, "CATASTROPHIC"),
        ("×1.0001 loop (10k)", "10,000", 4, "Moderate"),
        ("÷7 ×60 then ×7 ×60", "120", 2, "Mild"),
        ("Quadratic small root", "~8", 12, "Severe"),
        ("0.001 × 100k additions", "100,000", 5, "Moderate"),
        ("√ ×50 then ² ×50", "100", 15, "CATASTROPHIC"),
        ("Harmonic series (50k)", "100,000", 4, "Moderate"),
        ("Logistic map (100 iter)", "300", 15, "CATASTROPHIC"),
        ("Mixed ops tower (390)", "390", 8, "Severe"),
        ("Fibonacci ratio (200)", "400", 2, "Mild"),
        ("Taylor e^20 (80 terms)", "240", 3, "Moderate"),
    ]

    for name, ops, lost, severity in scenarios:
        remaining = 15 - lost
        color = get_gradient_color(remaining)
        bar = make_precision_bar(remaining, width=30)

        if severity == "CATASTROPHIC":
            sev_text = Text("☠️  CATASTROPHIC", style="bold red")
            verdict = "💀"
        elif severity == "Severe":
            sev_text = Text("🔴 Severe", style="bold dark_orange")
            verdict = "⚠️"
        elif severity == "Moderate":
            sev_text = Text("🟡 Moderate", style="bold yellow")
            verdict = "🟡"
        else:
            sev_text = Text("🟢 Mild", style="bold green")
            verdict = "✅"

        lost_text = Text()
        lost_text.append(f"{lost}", style=f"bold {color}")
        lost_text.append(f" / 15", style="dim")

        table.add_row(name, ops, lost_text, bar, verdict)

    console.print(table)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    # Title screen
    title_art = """
[bold bright_cyan]
  ╔══════════════════════════════════════════════════════════════════╗
  ║                                                                  ║
  ║   ████████╗██████╗  █████╗  ██████╗██╗  ██╗███████╗██████╗      ║
  ║   ╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██║ ██╔╝██╔════╝██╔══██╗    ║
  ║      ██║   ██████╔╝███████║██║     █████╔╝ █████╗  ██║  ██║     ║
  ║      ██║   ██╔══██╗██╔══██║██║     ██╔═██╗ ██╔══╝  ██║  ██║     ║
  ║      ██║   ██║  ██║██║  ██║╚██████╗██║  ██╗███████╗██████╔╝     ║
  ║      ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═════╝  ║
  ║                                                                  ║
  ║   ███████╗██╗      ██████╗  █████╗ ████████╗                     ║
  ║   ██╔════╝██║     ██╔═══██╗██╔══██╗╚══██╔══╝                    ║
  ║   █████╗  ██║     ██║   ██║███████║   ██║                        ║
  ║   ██╔══╝  ██║     ██║   ██║██╔══██║   ██║                        ║
  ║   ██║     ███████╗╚██████╔╝██║  ██║   ██║                        ║
  ║   ╚═╝     ╚══════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝                      ║
  ║                                                                  ║
  ╚══════════════════════════════════════════════════════════════════╝
[/]"""
    console.print(title_art)

    console.print(Panel(
        "[bold bright_white]🔬 Floating-Point Error Propagation Visualizer[/]\n\n"
        "[dim]IEEE 754 double-precision floats have ~15.9 decimal digits of precision.\n"
        "Every arithmetic operation can introduce up to 0.5 ULP of rounding error.\n"
        "This tool tracks the conservative interval [lo, hi] guaranteed to contain\n"
        "the true mathematical result, making invisible errors VISIBLE.[/]\n\n"
        "[bold]Legend:[/]\n"
        "  [bold bright_green]██████████████████████████████████████████[/]  15 digits — [bold green]Perfect[/]\n"
        "  [bold bright_green]██████████████████████[/][bold #ffcc00]▓▓▓▓▓[/][dim red]░░░[/][dim]··············[/]  10 digits — [bold yellow]Degraded[/]\n"
        "  [bold bright_green]██████████[/][bold #ffcc00]▓▓▓[/][dim red]░░░[/][dim]·························[/]   5 digits — [bold dark_orange]Poor[/]\n"
        "  [dim red]░░░[/][dim]······································[/]   0 digits — [bold red]Garbage[/] 💀\n\n"
        "  [bold white]●[/] = computed value    [bold]◄────────►[/] = uncertainty interval\n"
        "  [bold bright_green]Green digits[/] = reliable    [bold red]Red digits[/] = noise",
        title="[bold bright_cyan]How to Read the Output[/]",
        border_style="bright_cyan",
        padding=(1, 3),
    ))

    console.print()

    # Run all demos
    demo_repeated_addition()
    demo_catastrophic_cancellation()
    demo_multiplication_chain()
    demo_division_roundtrip()
    demo_quadratic()
    demo_massive_sum()
    demo_sqrt_roundtrip()
    demo_harmonic_series()
    demo_logistic_map()
    demo_tower_of_operations()
    demo_fibonacci_ratio()
    demo_exp_taylor()
    demo_comparison_table()

    # Final panel
    console.print()
    console.print(Panel(
        "[bold bright_green]🎓 Key Takeaways:[/]\n\n"
        "  [bold]1.[/] Every float operation introduces [bold]≤ 0.5 ULP[/] rounding error\n"
        "  [bold]2.[/] [bold red]Catastrophic cancellation[/] (subtracting near-equal values) is the #1 killer\n"
        "  [bold]3.[/] [bold red]Chaotic systems[/] amplify errors exponentially — prediction becomes impossible\n"
        "  [bold]4.[/] [bold yellow]Long loops[/] accumulate error — 100k additions can lose ~5 digits\n"
        "  [bold]5.[/] [bold yellow]Round-trips[/] (÷ then ×, √ then ²) never fully recover lost precision\n"
        "  [bold]6.[/] [bold yellow]Large intermediate values[/] that cancel (Taylor series) waste precision\n\n"
        "[bold bright_cyan]🛡️ Defenses:[/]\n\n"
        "  • [bold cyan]math.fsum()[/]         — Compensated summation for accurate sums\n"
        "  • [bold cyan]decimal.Decimal[/]     — Exact decimal arithmetic (no binary surprises)\n"
        "  • [bold cyan]mpmath[/]              — Arbitrary-precision floating point\n"
        "  • [bold cyan]Kahan summation[/]     — Track and compensate rounding errors in loops\n"
        "  • [bold cyan]Reformulate algebra[/] — Avoid cancellation (e.g., x₂ = c/(a·x₁))\n"
        "  • [bold cyan]Interval arithmetic[/] — Libraries like [bold]python-flint[/] or [bold]mpfi[/]\n\n"
        "[dim italic]\"God made the integers; all else is the work of man.\" — Leopold Kronecker\n"
        "\"...and man made floating-point, which was the work of the devil.\" — Every numerical analyst ever[/]",
        title="[bold bright_yellow]📝 Summary & Recommendations[/]",
        border_style="bright_yellow",
        padding=(1, 3),
    ))

    console.print()
    console.print(Align.center(
        Text("Made with TrackedFloat 🔬 — Making the invisible visible\n",
             style="dim italic")
    ))
