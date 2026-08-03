---
description: Initialize or repair the worker workspace and optionally install the pen.dev CLI.
---

Run the following from the workspace root:

```bash
./scripts/initx.sh
```

This command creates required directories, initializes Git when necessary, and creates these relative links when absent:

- `CLAUDE.md -> AGENTS.md`
- `.claude/skills -> ../.agents/skills`

It never replaces an existing non-link file or a link with a different target; report any skipped item.

To install the current pen.dev CLI (`@pen.dev/cli`, Node.js 18+), run:

```bash
./scripts/initx.sh --install-pen-cli
```

The Pencil MCP server is supplied by the activated pen.dev desktop application. Start that application first; then launch Codex and check `/mcp` for `pencil`. If it is absent, report that the desktop app needs installation, activation, or restart rather than fabricating an MCP configuration.
