"""spindle-gtm — local, single-founder GTM outreach engine.

Safety invariants (see docs/adr/0002 and CLAUDE.md):
- Apollo is the system of record and is READ-ONLY from this tool.
- Every external action is dry-run unless ``--apply`` is passed AND a human approves.
- No LinkedIn automation. PII never leaves the local machine or enters git.
"""

__version__ = "0.1.0"
