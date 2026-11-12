# Antigravity Developer Tooling Record — PLUTO vProctor

**Recorded:** 2026-11-11  
**Reference Setup Spec:** [ANTIGRAVITY_TOOLS_SETUP.md](../PLUTO_vProctor_Upgrade_Pack_v2/PLUTO_vProctor_Upgrade_Pack/ANTIGRAVITY_TOOLS_SETUP.md)  
**Host Environment:** Windows, Node.js `v24.13.0`, Antigravity CLI `agy.exe` `1.5.5` (`C:\Users\Sarthak\.gemini\bin\agy.exe`), Language Server `cli-2.31.0`.

---

## Summary Matrix

| Tool | Version / Revision | Install Scope | Install Method Executed | Live Verification Status | Reload / Notes |
|---|---|---|---|---|---|
| **GSD** (`get-shit-done-cc`) | `1.42.3` (`full` profile) | Project-local (`./.agent`) | `npx -y get-shit-done-cc@latest --antigravity --local` | **INSTALLED & VERIFIED** (`67` skills discovered by Antigravity LS; `33` agents; `gsd-tools.cjs` verified) | Reload Antigravity IDE to activate workspace hooks; invoke via `/gsd-help` (Antigravity skill format); upstream npm package carries deprecation warning; `gsd-sdk` shim written to `E:\AI_Workspace\node_global` (not on default `PATH`). |
| **Superpowers** (`obra/superpowers`) | `7.0.2` (commit `22f0b46`) | Global (`C:\Users\Sarthak\.gemini\config\plugins\superpowers`) | `C:\Users\Sarthak\.gemini\bin\agy.exe plugin install https://github.com/obra/superpowers` | **INSTALLED & VERIFIED** (`15` skills confirmed via `agy plugin list --json`, LS `GetAllPlugins`, and LS `GetAllSkills`) | Reload Antigravity IDE if skills do not immediately surface in new chat sessions; `agy plugin install` installs globally only (no `--local` flag in `agy plugin` CLI). |
| **Context7** (`https://mcp.context7.com/mcp`) | Remote MCP Server `4.5.0` | Global (`C:\Users\Sarthak\.gemini\config\mcp_config.json`) | `C:\Users\Sarthak\.gemini\bin\agy.exe mcp add --type http context7 https://mcp.context7.com/mcp` | **CONFIGURED & LIVE-VERIFIED** (`agy mcp list` shows `enabled`; direct MCP JSON-RPC returned `HTTP 200`; post-reload Antigravity `call_mcp_tool` verified both `resolve-library-id` and `query-docs` against FastAPI) | Live in Antigravity IDE MCP runtime after reload. Optional OAuth / API key setup was not needed and no credentials were stored in project files. |

---

## 1. GSD (Get Shit Done)

- **Official Source:** `https://github.com/gsd-build/get-shit-done`
- **Package & Version:** `get-shit-done-cc@1.42.3` (`.agent/get-shit-done/VERSION` = `1.42.3`, `.agent/.gsd-profile` = `full`)
- **Install Scope:** Project-local (`D:\_TY\MDM\PLUTO-vProctor\.agent\`) plus user defaults at `C:\Users\Sarthak\.gsd\defaults.json` (`{"resolve_model_ids": "omit"}`).
- **Command Executed (from repository root):**
  ```powershell
  npx -y get-shit-done-cc@latest --antigravity --local
  ```
- **Installed Artifacts:**
  - `.agent/skills/gsd-*/SKILL.md` (`67` Antigravity skills, including `.agent/skills/gsd-help/SKILL.md` referencing `@.agent/get-shit-done/workflows/help.md`)
  - `.agent/agents/` (`33` agent definitions)
  - `.agent/get-shit-done/` (core workflows, templates, references, `CHANGELOG.md`, `VERSION`, `bin/shared/model-catalog.json`)
  - `.agent/hooks/` & `.agent/settings.json` (`SessionStart`, `BeforeTool`, `AfterTool` hooks configured)
  - `.agent/package.json` (`{"type":"commonjs"}`), `.agent/gsd-file-manifest.json`, `.agent/gsd-install-state.json`
- **Verification Results:**
  - `.agent/get-shit-done/VERSION` reads `1.42.3`.
  - Antigravity Language Server `GetAllSkills` RPC discovered **67** `gsd-*` skills (`gsd-add-tests`, `gsd-ai-integration-phase`, `gsd-audit-fix`, `gsd-audit-milestone`, `gsd-audit-uat`, etc.).
  - `node "D:\_TY\MDM\PLUTO-vProctor\.agent\get-shit-done\bin\gsd-tools.cjs" --help` exited with code `0` and listed all CLI subcommands.
- **Warnings / Notes (Reported Accurately):**
  - `npm` emitted: `npm warn deprecated get-shit-done-cc@1.42.3: Package no longer supported.` (kept per setup rule not to silently substitute another package).
  - Installer warned that `gsd-sdk` shim was written to `E:\AI_Workspace\node_global`, which is currently not on `PATH` (workflows invoking `gsd-sdk` directly require adding `E:\AI_Workspace\node_global` to `PATH` or installing globally).
  - Antigravity registers GSD commands as hyphenated skills (`/gsd-help`, `gsd-help` skill) converted from `/gsd:help`. Reload Antigravity IDE and invoke `/gsd-help` inside a fresh chat turn to confirm interactive slash invocation.

---

## 2. Superpowers

- **Official Source:** `https://github.com/obra/superpowers`
- **Version / Revision:** `7.0.2` (git commit `22f0b46`: `Release v7.0.2: brainstorming tuning, harness bootstrap fixes, SDD helper fixes (#2657)`)
- **Install Scope:** Global Antigravity plugin (`C:\Users\Sarthak\.gemini\config\plugins\superpowers`). Note: `agy.exe plugin install` does not expose a `--local` flag; it clones directly into Antigravity's global plugin directory (`~/.gemini/config/plugins/`).
- **Commands Executed:**
  ```powershell
  & "C:\Users\Sarthak\.gemini\bin\agy.exe" plugin install https://github.com/obra/superpowers
  & "C:\Users\Sarthak\.gemini\bin\agy.exe" plugin list --json
  ```
- **Verification Results:**
  - `agy plugin install` cloned `https://github.com/obra/superpowers.git` and reported `[ok] superpowers — 15 installed`.
  - `agy plugin list --json` confirmed: `"name": "superpowers"`, `"enabled": true`, `"version": "7.0.2"`, `"source": "antigravity"`, `15` skills:
    `brainstorming`, `diagnosing-superpowers`, `dispatching-parallel-agents`, `executing-plans`, `finishing-a-development-branch`, `receiving-code-review`, `requesting-code-review`, `subagent-driven-development`, `systematic-debugging`, `test-driven-development`, `using-git-worktrees`, `using-superpowers`, `verification-before-completion`, `writing-plans`, `writing-skills`.
  - `.antigravity-plugin/plugin.json` confirms `"displayName": "Superpowers"`, `"version": "7.0.2"`.
  - Antigravity Language Server `GetAllPlugins` RPC returned `superpowers` (`disabled: False`, `isGlobal: True`, `skills_count: 15`) and `GetAllSkills` RPC discovered all `15` skill paths live.

---

## 3. Context7

- **Official Docs Referenced:** `https://context7.com/docs/installation` and `https://antigravity.google/docs/mcp` (plus built-in `agy-customizations/docs/mcp_servers.md`)
- **Server Version:** Context7 Remote MCP Server `4.5.0` (`https://mcp.context7.com/mcp`)
- **Install Scope:** Global Antigravity MCP config (`C:\Users\Sarthak\.gemini\config\mcp_config.json`). Note: Antigravity (`~/.gemini/config/mcp_config.json`) reads MCP configurations globally (`agy mcp add` writes directly to this file; no workspace-local `mcp_config.json` flag exists in `agy mcp add`).
- **Commands Executed:**
  ```powershell
  & "C:\Users\Sarthak\.gemini\bin\agy.exe" mcp add --type http context7 https://mcp.context7.com/mcp
  & "C:\Users\Sarthak\.gemini\bin\agy.exe" mcp list
  ```
- **Resulting `C:\Users\Sarthak\.gemini\config\mcp_config.json`:**
  ```json
  {
    "mcpServers": {
      "context7": {
        "disabled": false,
        "serverUrl": "https://mcp.context7.com/mcp"
      }
    }
  }
  ```
- **Verification Results:**
  - `agy.exe mcp list` reported: `context7 | http | enabled | https://mcp.context7.com/mcp`.
  - Direct Streamable HTTP JSON-RPC `initialize` request to `https://mcp.context7.com/mcp` returned `HTTP 200` with `serverInfo`: `{"name": "Context7", "title": "Context7", "version": "4.5.0"}`.
  - Direct JSON-RPC `tools/list` request returned `HTTP 200` with both MCP tools: `resolve-library-id` (`Resolve Context7 Library ID`) and `query-docs` (`Query Documentation`).
- **Notes & Reload / Optional Auth:**
  - In the pre-reload Language Server session, `GetMcpServerStates` returned `{}` because `mcp_config.json` was updated mid-session. **Reload Antigravity** (or click Refresh in `... > MCP Servers`) to attach the `context7` tools into the active session.
  - Note: Context7 is also listed in the Antigravity Marketplace (`antigravity-plugins-partners/plugin/context7`) and via `npx ctx7@0.11.0 setup --cli --antigravity` (browser OAuth + `find-docs` skill). Neither additional install was forced so as to avoid duplicate server IDs or storing credentials; use the official Antigravity browser OAuth flow later only if higher API rate limits are desired.

---

## 4. Safety & Non-Destructive Preservation Checks

- Verified `git diff -- backend/requirements.txt frontend/package.json .agent/rules .agent/workflows` returned empty:
  - Application runtime dependencies (`backend/requirements.txt`, `frontend/package.json`) were **not modified**.
  - Existing PLUTO vProctor rules (`.agent/rules/00-hardware-and-llm.md` .. `03-antigravity-working-style.md`) and workflows (`.agent/workflows/phase-0-setup.md` .. `run-all-evals.md`) were **preserved untouched**.
- Workspace trust, permissions, and execution policies were not disabled or bypassed.
- No secrets, API keys, or credentials were requested or written into project files.
- Feature implementation was **not** started (awaiting Antigravity reload + Phase 0 audit).

