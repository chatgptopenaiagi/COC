# Mission 001 engineering ledger

Last verified: 2026-11-19, Windows x64. Milestone: **0.1.0-alpha.2**.
The local engine is executable; the full universal-engine mission remains open.

| Area | Status | Execution evidence |
|---|---|---|
| Go broker / SQLite durability | PASS | Go tests; real host, authorization, crash and fault tests |
| Rust native library / IPC / supervision | PASS | Cargo, native host, stdio and loaded DLL ABI |
| Python SDK / orchestration / context / budgets | PASS | Unit and integration suites |
| Java SDK / H2 enterprise host | PASS | JDK 21-targeted compilation, contracts, actual invoices |
| JavaScript / TypeScript | PASS | Build, tests, actual Node and browser hosts |
| Django administration | PASS | Real broker, staff authentication and CSRF |
| Operator panel / strict CSP | PASS | Playwright desktop/mobile and real Codex chat |
| MCP tools bridge | PASS, limited scope | Real admission; completion through COC |
| Existing Codex server reuse | PASS | New logical thread, two-host live browser chat |
| Owned Codex server alternative | PASS | Real tools, two contexts, repair and usage |
| Codex cancellation | PASS | Parent/child cancellation and interrupted turn |
| Completed-thread reconnect | PASS | Same thread resumed, external server retained |
| Active-turn disconnect/recovery | NOT TESTED | Never automatically retry uncertain model work |
| Bounded repair lab | PASS | Real seeded defect, isolated correction, five-case oracle |
| Direct OpenAI authentication / model discovery | PASS | Diagnostic receipt |
| Direct OpenAI inference | BLOCKED | HTTP 429 quota/billing; three requests exhausted |
| Existing llama.cpp inference | BLOCKED | Endpoint requires separately authorized credential |
| Other provider adapters | NOT TESTED live | Implemented abstractions, no access assumed |
| Android runtime/demo | NOT TESTED | SDK unavailable; desktop Codex is not an Android runtime |
| Linux runtime | PASS in GitHub CI | evidence/platforms/linux/summary.json |
| Package extraction / publication | See release receipt | evidence/releases/latest.json is authoritative |

The complete default Python regression contains 30 cases: 25 passed and five
live tests skipped. Four separate Codex live tests passed; the direct API test
is blocked. Default VERIFY does not rerun inference. Actual logs, JUnit XML,
screenshots and structured receipts are retained under evidence/.

## Reference investigation

DRAGONHYDRA was inspected read-only. Request/session/receipt correlation and the
retained 21-test log are supported by source and artifacts. Those were unit
tests, not 21 live Codex round trips. Historical process reuse lacks full PID/birth
telemetry. COC separately verified its own existing-server reuse. See the report
under docs/research/DRAGONHYDRA-CODEX-BRIDGE-REFERENCE.md.

## Boundaries and continuation

All seven technologies remain implemented. There is no DRAGONHYDRA runtime
dependency. Credentials and private databases are ignored/excluded. Never reset
.runtime/openai-integration-budget.sqlite to retry paid inference; a new explicit
budget is required. No real clinical data was used.

Further work includes active-turn reconciliation, stronger process-tree resource
containment, signed evidence, storage retention/scale testing, Android verification,
broader provider live tests, credential rotation and hardened remote/multi-tenant
deployment. A2A, Manus and a Spring starter are not implemented. Two unrelated
applications support portability; they do not prove universal compatibility.

Resume from this ledger, evidence/acceptance.json, release evidence and Git status.
Preserve earlier evidence and private runtime state. Do not recreate functioning
kernels, modify DRAGONHYDRA or alter Codex configuration.
