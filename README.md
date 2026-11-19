# COC — CODEX INSIDE CODEX

An application integration engine with a Go coordination broker, Rust native
boundary, Python agent orchestration and interoperable Java, JavaScript and
TypeScript clients. Django provides optional authenticated administration.

**Engineering prerelease: 0.1.0-alpha.2.** This is executable software with live
integration evidence. It is not a production-ready universal application adapter.
Applications explicitly publish tools; the engine does not acquire arbitrary
application or operating-system privileges.

## Demonstrated

- Real Codex App Server inference invokes scientific application tools through
  durable parent/child COC tasks and returns correlated execution receipts.
- The existing current-user App Server can host another logical application
  thread. COC disconnects/reconnects without terminating that shared process.
- A browser chat request invokes both independent Python and JavaScript hosts.
- Java invoices use a real H2 database; Rust executes a native calculation and
  exposes authenticated stdio IPC and a C ABI validator.
- The repair laboratory reproduces a deliberate defect, accepts a model-proposed
  expression in an isolated copy, and passes an independent five-case oracle.
- Cancellation, peer loss, uncertain outcomes, idempotency, restart recovery,
  event persistence, scope checks and audit tamper detection have executable tests.

Evidence: [acceptance report](evidence/acceptance.json),
[Codex integration](docs/integration/COC-CODEX-LIVE-INTEGRATION.md),
[reference investigation](docs/research/DRAGONHYDRA-CODEX-BRIDGE-REFERENCE.md),
[implementation ledger](STATUS.md).

## Start on Windows

Use PowerShell 7, Python 3.12+, Go 1.26+, Rust/Cargo with MSVC build tools,
JDK 21+, Node 22+ and npm. Development was verified on Windows x64; exact
versions and individual results are recorded in evidence. Codex is needed only
for the Codex connector, and Django only for administration.

```powershell
cd C:\xampp\COC
./COC.ps1 INSTALL
./COC.ps1 VERIFY
./COC.ps1 START -Demo -Codex
./COC.ps1 OPEN
./COC.ps1 STATUS
./COC.ps1 STOP
```

`OPEN` opens the local operator panel using a single-use, 60-second login code.
The browser credential remains in memory. A provider API key is never a panel
credential. `START` alone starts just the broker; `-Demo` adds four host processes;
`-Codex` connects to an available current-user Codex control socket and permits
only the configured scientific and text tools. It creates a logical thread only
when an operator submits a task. No provider API inference runs automatically.

The broker normally listens at `http://127.0.0.1:7310`. Use `-Port` to change it.
Runtime data stays under `.runtime/installation`; STOP preserves the database.
`RECOVER` lists uncertain tasks and does not automatically replay their effects.

For an explicit isolated Codex process, run `coc-orchestrator --owned` with scoped
`COC_URL`, `COC_AGENT`, `COC_TOKEN` and explicit `--allow host:tool` arguments.
The default connector prefers an existing control socket; it does not inject
commands into terminals or read another agent's conversation.

## Technology status

| Technology | Functional component | Verification |
|---|---|---|
| Go | HTTP JSON-RPC broker, SQLite WAL, identities, tasks, scopes, SSE, receipts | Go unit tests, real integration/fault tests |
| Rust | Native validator/library, stdio gateway, process supervision, host | Cargo tests, loaded DLL ABI, real broker round trips |
| Python | SDK, host workers, Codex connector, providers, context, repair | Unit/integration tests and separate live Codex tests |
| Django | Staff-authenticated dashboard, task/evidence view, controlled administration | Real broker state, authentication and CSRF tests |
| Java | JVM SDK, host lifecycle, H2 invoice and synthetic healthcare example | JDK build, contract corpus and actual execution |
| JavaScript | Node host and browser capability execution | Actual Node/browser workers and JS tests |
| TypeScript | Typed SDK/declarations, validation, SSE, operator panel | Compilation, common corpus and Playwright |

## Provider boundaries

The verified live model integration is **Codex App Server 0.169.0**, authenticated
through the owner's existing Codex login. Dynamic host tools are an official
experimental API. Owned stdio and existing Unix-control-socket modes are distinct.

Direct OpenAI authentication and model discovery passed. **Direct inference is
BLOCKED by quota/billing.** Three bounded diagnostic requests exhausted the
authorized test allowance; the durable ledger prevents more. A fresh authorized
budget is required before another paid test. Do not delete the ledger to bypass it.

The existing llama.cpp endpoint requires its own authorized credential; live local
inference remains blocked pending configuration. No model was downloaded. HTTP
adapters also support configured Anthropic, xAI, Microsoft Azure and compatible
local/Ollama endpoints. Their live access is not claimed. Manus and A2A remain
future integrations; unsupported operations raise explicit errors.

## Documentation and commands

[Architecture](ARCHITECTURE.md) · [Development](DEVELOPMENT.md) ·
[Security](SECURITY.md) · [Governance](GOVERNANCE.md) ·
[Protocol](specifications/protocol/COC-PROTOCOL-1.md) ·
[SDK usage](docs/sdk/INTEGRATION.md) · [Operations](docs/operations/RUNBOOK.md)

`BUILD`, `TEST`, `VERIFY`, `START`, `STOP`, `STATUS`, `DOCTOR`, `RECOVER`,
`PACKAGE`, `INSTALL`, `OPEN` are implemented by `COC.ps1`. Default testing uses no
paid inference. Live tests require explicit environment flags and retain separate
receipts. A passing default suite does not mean skipped live tests ran again.

COC is independent of DRAGONHYDRA. That project's code, credentials, executables
and databases are not required or included.
