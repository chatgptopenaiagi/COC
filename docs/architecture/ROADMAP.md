# Implementation boundaries and next milestones

## Delivered core

Go owns task authority and SQLite persistence. Rust supplies the native ABI,
stdio bridge and process supervision. Python supplies orchestration, context,
providers, repair and Codex integration. Java, JS and TS host SDKs use the common
protocol. Django is optional administration. The TypeScript panel is usable
without Django. Two logical Codex contexts do not require duplicate installations.

The primary embedding model is a local broker plus small application adapters:
process isolation and language neutrality cost an RPC hop. In-process SDKs avoid
that hop inside the host but share its failure boundary. Remote TLS clients reuse
the protocol with added latency, deployment and credential requirements. This
alpha is verified for local Windows use, with Linux CI maintained separately.

## Remaining engineering

1. Reconcile active Codex turns after lost tool-response acknowledgements; verify
   event gaps and ownership under multiple clients. Preserve uncertain outcomes.
2. Add host process restart policies, OS process-tree limits, credential rotation,
   pagination, indexing and controlled evidence retention. Benchmark growing task
   histories before claiming high-scale operation.
3. Verify Linux artifacts on native runners, then Android network-client transport
   and Rust ABI using an available Android SDK/NDK. Android background execution
   and app lifecycle need platform-specific handling; no desktop Codex port is assumed.
4. With separately authorized credentials/budgets, verify local llama.cpp and
   optional paid providers. Keep direct OpenAI testing locked until a fresh budget
   is approved. Add A2A/Manus only against supported documented interfaces.
5. Add reviewed enterprise/Spring and domain adapters. These must expose selected
   functions rather than grant blanket database, OS or application privileges.
6. Design signed evidence export, remote identity federation and stronger
   multi-tenant isolation before a production release. High-assurance healthcare
   and industrial integration need independent security/operational review.

## Use-case fit

Software engineering and scientific calculations are demonstrated. Sports
analytics can expose bounded statistics/import functions with dataset provenance.
Finance needs read-only analysis and independently checked calculations before
any trading authority. Industrial monitoring should initially expose observations,
not actuator control. Enterprise workflows need business idempotency/transactions.
Healthcare remains synthetic administrative integration. These are candidate
adapter directions, not seven verified industry deployments.

Codex App Server, MCP, JSON-RPC, language SDKs and task schedulers already supply
many ingredients. COC's contribution is their application-independent composition
with explicit parent/child ownership, shared receipts and bounded repair workflows.
No claim is made that nested agents themselves are unprecedented.
