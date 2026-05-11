import math
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import track
from rich import box

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
# Rich visualization helpers
# ============================================================

def digit_color(digits):
    """Return a color based on how many reliable digits remain."""
    if digits >= 14:
        return "bright_green"
    elif digits >= 12:
        return "green"
    elif digits >= 10:
        return "yellow"
    elif digits >= 7:
        return "dark_orange"
    elif digits >= 4:
        return "red"
    elif digits >= 1:
        return "bright_red"
    else:
        return "reverse red"


def uncertainty_bar(digits, max_digits=15, bar_width=30):
    """Create a visual bar showing how much precision remains."""
    filled = int((digits / max_digits) * bar_width)
    filled = max(0, min(bar_width, filled))
    empty = bar_width - filled
    color = digit_color(digits)
    bar = f"[{color}]{'█' * filled}[/{color}][dim]{'░' * empty}[/dim]"
    return bar


def format_row(label, tf, expected=None):
    """Format a TrackedFloat as a rich table row."""
    digits = tf.accurate_digits
    color = digit_color(digits)
    bar = uncertainty_bar(digits)

    value_str = f"{tf.value:.17g}"
    lo_str = f"{tf.lo:.17g}"
    hi_str = f"{tf.hi:.17g}"
    unc_str = f"±{tf.uncertainty / 2:.2e}"
    digits_str = f"[{color}]{digits}[/{color}]"

    row = [
        label,
        value_str,
        f"[dim]{lo_str}[/dim]",
        f"[dim]{hi_str}[/dim]",
        unc_str,
        digits_str,
        bar,
    ]
    if expected is not None:
        row.append(f"{expected}")
    return row


def make_table(title, rows, show_expected=False):
    """Build a Rich table from rows."""
    table = Table(
        title=title,
        box=box.ROUNDED,
        title_style="bold bright_cyan",
        header_style="bold white on dark_blue",
        show_lines=True,
        padding=(0, 1),
    )
    table.add_column("Step", style="bold", min_width=16)
    table.add_column("Value", style="cyan", min_width=22)
    table.add_column("Lower Bound", min_width=24)
    table.add_column("Upper Bound", min_width=24)
    table.add_column("± Uncertainty", style="magenta", min_width=14)
    table.add_column("Digits", justify="center", min_width=6)
    table.add_column("Precision", min_width=32)
    if show_expected:
        table.add_column("Expected", style="bright_yellow", min_width=12)

    for row in rows:
        table.add_row(*row)

    return table


# ============================================================
# DEMOS
# ============================================================

def demo_repeated_addition():
    """Example 1: Summing 0.1 repeatedly."""
    rows = []
    total = TrackedFloat(0.1)
    rows.append(format_row("0.1 × 1", total, "0.1"))
    for i in range(2, 21):
        total = total + TrackedFloat(0.1)
        expected = round(i * 0.1, 10)
        if i <= 10 or i % 5 == 0:
            rows.append(format_row(f"0.1 × {i}", total, str(expected)))

    table = make_table(
        "🔢 Example 1: Summing 0.1 repeatedly (should reach 2.0 at ×20)",
        rows, show_expected=True,
    )
    console.print(table)
    console.print(
        f"  [bold yellow]⚠ After 20 additions:[/] uncertainty = "
        f"[bold red]±{total.uncertainty / 2:.2e}[/], "
        f"reliable digits ≈ [bold]{total.accurate_digits}[/]\n"
    )


def demo_catastrophic_cancellation():
    """Example 2: Subtracting nearly equal numbers."""
    rows = []
    epsilons = [1e-5, 1e-8, 1e-10, 1e-12, 1e-14, 1e-15]
    for eps in epsilons:
        a = TrackedFloat(1.0) + TrackedFloat(eps)
        b = a - TrackedFloat(1.0)
        label = f"(1+{eps:.0e})-1"
        rows.append(format_row(label, b, f"{eps:.0e}"))

    table = make_table(
        "💥 Example 2: Catastrophic Cancellation — (1 + ε) - 1",
        rows, show_expected=True,
    )
    console.print(table)
    console.print(
        "  [bold red]⚠ As ε shrinks, subtracting nearly-equal numbers "
        "destroys almost ALL significant digits![/]\n"
    )


def demo_multiplication_chain():
    """Example 3: Repeated multiplication."""
    rows = []
    x = TrackedFloat(1.0)
    factor = TrackedFloat(1.0001)
    for i in range(1, 10001):
        x = x * factor
        if i in [1, 10, 50, 100, 500, 1000, 2000, 5000, 10000]:
            rows.append(format_row(f"1.0001^{i}", x))

    table = make_table(
        "📈 Example 3: Multiplying by 1.0001 in a loop (10,000 times)",
        rows,
    )
    console.print(table)
    console.print(
        f"  [bold yellow]⚠ After 10,000 multiplications:[/] uncertainty = "
        f"[bold red]±{x.uncertainty / 2:.2e}[/], "
        f"reliable digits ≈ [bold]{x.accurate_digits}[/]\n"
    )


def demo_division_chain():
    """Example 4: Repeated division and multiplication."""
    rows = []
    val = TrackedFloat(1.0)
    rows.append(format_row("Start", val, "1.0"))

    for i in range(1, 51):
        val = val / TrackedFloat(3.0)
        if i in [1, 5, 10, 25, 50]:
            rows.append(format_row(f"÷3 ×{i}", val))

    for i in range(1, 51):
        val = val * TrackedFloat(3.0)
        if i in [1, 5, 10, 25, 50]:
            rows.append(format_row(f"×3 ×{i} (back)", val, "1.0" if i == 50 else ""))

    table = make_table(
        "🔄 Example 4: Divide by 3 fifty times, then multiply back",
        rows, show_expected=True,
    )
    console.print(table)
    console.print(
        f"  [bold yellow]⚠ Round-trip result:[/] uncertainty = "
        f"[bold red]±{val.uncertainty / 2:.2e}[/], "
        f"reliable digits ≈ [bold]{val.accurate_digits}[/]\n"
    )


def demo_quadratic():
    """Example 5: Quadratic formula with near-cancellation."""
    rows = []
    a = TrackedFloat(1.0)
    b = TrackedFloat(-1000000.001)
    c = TrackedFloat(1.0)

    b2 = b ** 2
    rows.append(format_row("b²", b2))
    four_ac = TrackedFloat(4.0) * a * c
    rows.append(format_row("4ac", four_ac))
    disc = b2 - four_ac
    rows.append(format_row("b² - 4ac", disc))
    sq = disc.sqrt()
    rows.append(format_row("√(b²-4ac)", sq))

    x1 = (-b + sq) / (TrackedFloat(2.0) * a)
    x2 = (-b - sq) / (TrackedFloat(2.0) * a)
    rows.append(format_row("x1 (large)", x1))
    rows.append(format_row("x2 (small)", x2))

    table = make_table(
        "📐 Example 5: Quadratic x² - 1000000.001x + 1 = 0",
        rows,
    )
    console.print(table)
    console.print(
        f"  [bold red]⚠ x2 (small root) has only ~{x2.accurate_digits} "
        f"reliable digits due to cancellation![/]\n"
    )


def demo_massive_sum():
    """Example 6: Summing 0.001 one hundred thousand times."""
    rows = []
    total = TrackedFloat(0.0)
    milestones = {1, 10, 100, 1000, 5000, 10000, 25000, 50000, 100000}

    for i in range(1, 100001):
        total = total + TrackedFloat(0.001)
        if i in milestones:
            expected = i * 0.001
            rows.append(format_row(f"+0.001 ×{i:>6d}", total, f"{expected:.3f}"))

    table = make_table(
        "🏔️  Example 6: Summing 0.001 × 100,000 (should reach 100.0)",
        rows, show_expected=True,
    )
    console.print(table)
    console.print(
        f"  [bold yellow]⚠ After 100,000 additions:[/] uncertainty = "
        f"[bold red]±{total.uncertainty / 2:.2e}[/], "
        f"reliable digits ≈ [bold]{total.accurate_digits}[/]\n"
    )


def demo_recursive_sqrt():
    """Example 7: Repeated sqrt then squaring back."""
    rows = []
    val = TrackedFloat(2.0)
    rows.append(format_row("Start", val, "2.0"))

    for i in range(1, 51):
        val = val.sqrt()
        if i in [1, 5, 10, 20, 30, 40, 50]:
            rows.append(format_row(f"√ ×{i}", val))

    for i in range(1, 51):
        val = val ** 2
        if i in [1, 10, 20, 30, 40, 50]:
            rows.append(format_row(f"² ×{i} (back)", val, "2.0" if i == 50 else ""))

    table = make_table(
        "🌀 Example 7: √2 fifty times, then square back (should return to 2.0)",
        rows, show_expected=True,
    )
    console.print(table)
    console.print(
        f"  [bold yellow]⚠ Round-trip result:[/] value = "
        f"[bold]{float(val):.17g}[/], uncertainty = "
        f"[bold red]±{val.uncertainty / 2:.2e}[/], "
        f"reliable digits ≈ [bold]{val.accurate_digits}[/]\n"
    )


def demo_harmonic_series():
    """Example 8: Partial sums of the harmonic series."""
    rows = []
    total = TrackedFloat(0.0)
    milestones = {1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000}

    for i in range(1, 50001):
        total = total + TrackedFloat(1.0) / TrackedFloat(float(i))
        if i in milestones:
            rows.append(format_row(f"H({i:>5d})", total))

    table = make_table(
        "📊 Example 8: Harmonic Series H(n) = Σ 1/k for k=1..50000",
        rows,
    )
    console.print(table)
    console.print(
        f"  [bold yellow]⚠ After 50,000 terms:[/] uncertainty = "
        f"[bold red]±{total.uncertainty / 2:.2e}[/], "
        f"reliable digits ≈ [bold]{total.accurate_digits}[/]\n"
    )


def demo_logistic_map():
    """Example 9: Chaotic logistic map x_{n+1} = r*x*(1-x)."""
    rows = []
    r = TrackedFloat(3.99)  # chaotic regime
    x = TrackedFloat(0.5)
    rows.append(format_row("x(0)", x))

    for i in range(1, 101):
        x = r * x * (TrackedFloat(1.0) - x)
        if i in [1, 2, 5, 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100]:
            rows.append(format_row(f"x({i})", x))

    table = make_table(
        "🌪️  Example 9: Chaotic Logistic Map x→3.99·x·(1-x) — chaos amplifies error!",
        rows,
    )
    console.print(table)
    console.print(
        f"  [bold red]⚠ Chaos + floating-point = total uncertainty after "
        f"~50-60 iterations![/]\n"
        f"  [dim]The logistic map at r=3.99 is chaotic: tiny errors grow "
        f"exponentially.[/]\n"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    console.print(Panel(
        "[bold bright_cyan]🔬 TRACKED FLOAT: Visualizing Floating-Point Error Propagation[/]\n\n"
        "[dim]Every operation widens the uncertainty interval.\n"
        "Watch the green precision bars shrink as errors accumulate![/]\n\n"
        "[bright_green]████████████████████████████████[/] = 15 digits (perfect)\n"
        "[yellow]████████████████░░░░░░░░░░░░░░░░[/] = ~10 digits\n"
        "[red]████████░░░░░░░░░░░░░░░░░░░░░░░░[/] = ~4 digits\n"
        "[reverse red]░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░[/] = 0 digits (garbage)",
        title="[bold white]Legend[/]",
        border_style="bright_cyan",
        padding=(1, 2),
    ))

    console.print()
    demo_repeated_addition()
    demo_catastrophic_cancellation()
    demo_multiplication_chain()
    demo_division_chain()
    demo_quadratic()
    demo_massive_sum()
    demo_recursive_sqrt()
    demo_harmonic_series()
    demo_logistic_map()

    console.print(Panel(
        "[bold bright_green]Key Takeaways:[/]\n\n"
        "• [bold]Every float operation[/] introduces up to 0.5 ULP of rounding error [[1]]\n"
        "• [bold]Addition/subtraction[/] of nearly-equal values causes [bold red]catastrophic cancellation[/] [[2]]\n"
        "• [bold]Long loops[/] accumulate error — 100k additions can lose ~4 digits\n"
        "• [bold]Chaotic systems[/] (logistic map) amplify errors exponentially\n"
        "• [bold]Round-trips[/] (÷3 then ×3) never fully recover lost precision\n"
        "• Use [bold cyan]math.fsum()[/] for accurate summation [[1]]\n"
        "• Use [bold cyan]decimal.Decimal[/] when exact decimal arithmetic matters [[9]]",
        title="[bold white]📝 Summary[/]",
        border_style="bright_yellow",
        padding=(1, 2),
    ))
