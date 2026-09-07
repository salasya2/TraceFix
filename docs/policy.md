# Repository policy

Administrators approve policy documents stored in TraceFix. A failed branch, PR description, log, or `AGENTS.md` cannot grant permissions.

Line limits count **additions plus deletions**. Paths are normalized to POSIX form before matching. `**` matches across directories; a trailing `/` is a prefix match.

See `packages/policy/src/tracefix/policy/schema.py` for the authoritative schema and platform maximums.
