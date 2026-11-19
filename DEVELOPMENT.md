# Development and verification

Run `./COC.ps1 INSTALL`, then `./COC.ps1 VERIFY` from the repository root.
Installation is project-local: `.venv`, npm dependencies, `.tools/java`. Existing
toolchains are reused. The build locates the project-local Rust installation when
present; otherwise Cargo must be on PATH. No Codex configuration is rewritten.

`BUILD` compiles Go, Rust, Java, TypeScript/operator UI, builds the Python wheel and
checks Django. `TEST` runs Go, Cargo, Java, JS and the complete Python suite,
including real broker subprocesses, SDK conformance, Django, MCP, security,
recovery and Playwright. JUnit is `evidence/tests/full-regression.xml`.
Both commands fail on required step failure. Logs and per-step statuses remain
available even after failure. `VERIFY` additionally scans publication files and
generates the acceptance report. It never silently counts skipped live tests as
passes.

Linux uses PowerShell 7 (`pwsh`), `.venv/bin/python`, standard Cargo/JDK/Node/Go,
and Chromium installed with `npx playwright install --with-deps chromium`.
The GitHub workflow executes the same core pipeline. Android has a separate
client/toolchain status; desktop Codex is not an Android runtime.

## Live tests

Each flag is intentionally separate; set it for the named file only:

| Flag | Test file | Effect |
|---|---|---|
| COC_LIVE_CODEX=1 | test_live_codex.py | Owned App Server, scientific operation and repair, two turns |
| COC_LIVE_CODEX_ACCOUNTING=1 | test_live_accounting.py | One owned-server turn and actual task token accounting |
| COC_LIVE_EXISTING=1 | test_existing_codex.py | Existing control socket, browser chat, two applications, detach/reconnect |
| COC_LIVE_CODEX_CANCEL=1 | test_codex_cancel.py | Real model tool invocation followed by hierarchical cancellation |
| COC_LIVE_OPENAI=1 | test_live_openai.py | Direct paid request, **currently blocked and not authorized for retry** |

Use a unique workspace below `.runtime/` with pytest `--basetemp`, and write a
separate JUnit report. Codex tests use the existing CLI login, not the provider key.
Default tests contain synthetic fixtures where appropriate; they are not live AI
evidence. Keep the direct-API ledger intact across sessions.

## Editing shared contracts

`specifications/schemas/message.schema.json` is authoritative. `npm run build`
generates Python/TypeScript copies and rebuilds the panel. Rust includes the same
schema. Java validates the contract vocabulary used by the COC envelope; arbitrary
JSON Schema vocabularies in host capabilities remain broker-validated. The shared
valid/invalid corpus must pass in every language after contract changes.

Do not modify DRAGONHYDRA. `scripts/audit-reference.py` reads a fixed allowlist of
reference source/evidence files only and writes its report under COC.
