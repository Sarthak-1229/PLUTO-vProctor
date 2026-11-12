# Antigravity Tooling Setup — PLUTO vProctor

The owner explicitly wants Antigravity to download/configure these tools itself. Use project-local scope where supported and install before Phase 0 audit.

## 1. GSD — planning and milestones
Official source: https://github.com/gsd-build/get-shit-done
From the repository root:
```powershell
npx get-shit-done-cc@latest --antigravity --local
```
Reload Antigravity and verify `/gsd:help`. Do not bypass permission prompts.

## 2. Superpowers — engineering workflow and TDD
Official source: https://github.com/obra/superpowers
If Antigravity CLI is available:
```powershell
agy plugin install https://github.com/obra/superpowers
agy plugin list
```
If `agy` is unavailable, read the current official Antigravity plugin instructions and use the Antigravity plugin UI. Do not use an unrelated Claude Code command or unofficial fork. Reload and verify skills.

## 3. Context7 — current library documentation
Official docs: https://context7.com/docs/installation
Antigravity MCP docs: https://antigravity.google/docs/mcp
Read both current official docs. Prefer Antigravity MCP Store installation; alternatively configure official endpoint `https://mcp.context7.com/mcp` using the documented Antigravity MCP flow. If Context7's current installer explicitly supports Antigravity CLI/skills mode, use its documented Antigravity command. Never invent MCP config keys. Complete OAuth only through the official browser flow; never ask for passwords or store credentials in project files.

## Safety and verification
- The owner authorizes installing these three developer tools.
- Use local/project scope where supported. Show exact commands when Antigravity requests approval.
- Do not disable workspace trust, bypass permissions or enable unrestricted execution.
- These are developer tools, NOT application runtime dependencies. Do not add them to `requirements.txt` or `package.json`.
- Preserve existing rules/workflows; merge compatible additions instead of overwriting.
- Record versions, install scope, verification and failures in `docs/ANTIGRAVITY_TOOLING.md`.
- Report failures accurately; do not silently substitute another package.
- Reload Antigravity, verify all tools, then proceed to Phase 0 audit only. Do not implement features until audit approval.
