"""Hard risk limits.

These live in code, never in a prompt. An LLM can be argued out of a guideline;
it cannot be argued out of a `min()`. Both the Risk Manager (which sets the
envelope) and the Portfolio Manager (which signs off on the final size) clamp
against the same ceiling, so no chain of confident-sounding reasoning can produce
a position larger than this.

The unit-vs-notional trap this closes: every size in the system is measured in
*units of the symbol*, and a unit is not a stable quantity of money. 10,000 units
is a plausible-looking equity position and a ~$630M Bitcoin position. An LLM asked
for "max units" without being told the price has no way to tell those apart -- so
the ceiling is computed here, from equity and price, rather than guessed there.
"""

from __future__ import annotations

MAX_POSITION_PCT_OF_EQUITY = 0.25


def max_affordable_units(equity: float, current_price: float) -> float:
    """The largest position, in units, worth at most MAX_POSITION_PCT_OF_EQUITY."""
    if current_price <= 0:
        return 0.0
    return (equity * MAX_POSITION_PCT_OF_EQUITY) / current_price
