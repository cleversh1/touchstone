"""The shared FastMCP instance.

Kept in its own module so that `tools` and `admin` can both register against it
without importing `server` (which would create a circular import).
"""

from fastmcp import FastMCP

mcp = FastMCP(
    name="Touchstone",
    instructions=(
        "Touchstone is your team's shared memory. Call recall() at the start of a "
        "marketing task to retrieve relevant brand-voice rules, process notes, and "
        "past decisions, and tell the user what you're applying before you respond. "
        "Call store() when you learn a durable convention, process step, or decision "
        "that a different team member would benefit from on a similar task."
    ),
)
