"""The simulated database terminal.

The student types commands into a console in the browser and sees terminal-style
output. The terminal is *simulated*: there is no shell, no filesystem and no
code execution. Every command is **parsed** into a small, fixed set of
operations and then carried out through the Django ORM.

That design is deliberate:

* `eval()` and raw SQL execution of typed input are never used, so nothing a
  student types can reach the machine or any table other than `students`;
* because commands are parsed rather than executed verbatim, the same command
  can be shown as SQL *and* as the equivalent ORM call, which is what the two
  terminal modes rely on.

Modules:
    result   — the structured result a command produces
    parsers  — the SQL and ORM parsers (text -> Command)
    engine   — executes a parsed Command and records it in the statement log
"""

from .engine import execute
from .result import Result

__all__ = ['execute', 'Result']
