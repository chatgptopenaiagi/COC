# DRAGONHYDRA Codex bridge: read-only reference investigation

Inspected 2026-11-19 for COC Mission 001, Addendum A. Reference root:
`C:/xampp/DRAGONHYDRA-CORE-NEXT-LAB/DRAGONHYDRA-SCRAPP-INTELLIGENCE`.
No reference code was imported, executed, edited, installed, or republished. Its
credentials, private runtime configuration and conversation history were not read.
Selected source/artifact hashes are in
[`evidence/research/dragonhydra-reference.json`](../../evidence/research/dragonhydra-reference.json).

## Reconstruction and classification

| Question | Observation and source, relative to reference root | Classification |
|---|---|---|
| Initiator | Engineering tab in `application/living/web/cockpit.js:53`; packaged UI exercised by `tests/mission006_operator_live.py:20` | VERIFIED from source |
| Request function | POST `/api/engineering/submit`, `application/living/server.py:88`, calls `Engineering.submit`, `codex_bridge.py:62` | VERIFIED |
| Discovery | Operator-selected socket and thread; default socket under current user's `.codex/app-server-control`; thread default from `CODEX_THREAD_ID` | VERIFIED; not general CLI discovery |
| Target identity | `thread/read` metadata, exact normalized workspace match, `thread/turns/list` metadata for the active turn; `codex_bridge.py:48` | VERIFIED |
| Transport | Windows AF_UNIX stream, WebSocket HTTP Upgrade, bidirectional App Server JSON-RPC | VERIFIED from source; documented transport |
| Delivery | `turn/steer` with `expectedTurnId` when active; `turn/start` when idle; other states blocked | VERIFIED from source |
| Recorded request | `evidence/mission-006/operator-live-20261119T080121Z/job.json`: job `f6cf4e74…`, thread `01a1f09d…`, turn `01a1f28d…`, submitted 08:01:32 UTC | VERIFIED artifact |
| Execution instruction | Read the existing unit-test log, report its count/result; explicitly no edits or test rerun | VERIFIED artifact |
| Actual executor PID | Neither request nor receipt records independently observed Codex PID or process-start telemetry | UNVERIFIED |
| Completion | Application polls a bounded JSON result file; matching job ID and status in PASS/FAIL/BLOCKED/PARTIAL updates the job | VERIFIED from source |
| Result generation | The instruction asks the existing Codex worker to save a redacted receipt. The bridge does not generate execution proof from App Server final events | VERIFIED from source |
| Receipt location | `evidence/mission-006/engineering-jobs/f6cf4e7457ee4155b1fbe28e7841cee8.result.json` | VERIFIED |
| Receipt correlation | Receipt job ID equals submitted job ID; result timestamp 08:01:45 UTC; operator test records the same receipt | VERIFIED |
| PASS meaning | The retained diagnostic reports the existing log correctly; it does not execute 21 new tests | VERIFIED |
| 21-test source | `evidence/mission-006/cockpit-unit-retest.log`: 21 tests, 33.395 seconds, final OK | VERIFIED by independent read |
| Nature of 21 tests | `tests/test_mission006_cockpit.py` includes synthetic provider fixtures and mocked bridge checks | VERIFIED; not 21 live Codex tests |
| Existing process reuse | Bridge has no Codex process-launch path; job/receipt assert existing worker; live test records successful submission | SUPPORTED BUT INCOMPLETE without PID trace |
| Additional Codex process | No launch in this bridge's source; absence across the whole workstation during the experiment cannot be independently established | SUPPORTED BUT INCOMPLETE |
| Recursive control | No evidence of nested agents, multiple application portability, or shared recursive ownership in this experiment | NOT SUPPORTED by these artifacts |

The original experiment is substantially better supported than a standalone receipt:
source, request, thread/turn IDs, result, live UI test and retained log agree. The
execution-process identity remains an evidentiary gap. COC does not upgrade the
receipt's self-reported process assertions into independently verified facts.

## Trust, ownership and limitations

Application HTTP routes require a local administrator credential or authenticated
browser session; browser writes require same origin and CSRF. The Codex connection
relies on current-user socket access. The bridge checks that its configured path
is inside the current user's Codex directory; that is not an independent audit of
the socket's ACL. No provider API key is used by this local bridge.

RPC calls are allowlisted. It reads thread metadata rather than conversation
content. Closing the WebSocket detaches; it does not kill the shared server.
Cancellation is not part of this bridge contract. Events unrelated to the current
RPC response are discarded. A matching result file is trusted after schema-like
checks, with no cryptographic binding to the Codex process or referenced log.
Loss of a submission acknowledgement can leave execution ambiguous; a fresh
submission generates a new ID and does not provide server-side deduplication.

## Independent COC implementation

COC implements the reusable principle using its own modules:

- `coc.codex_socket`: explicit endpoint discovery, metadata/workspace validation,
  authorized-thread attachment, reconnect/resume and connection-only detachment.
- `coc.codex`: owned stdio fallback, turn events, bounded calls, cancellation and
  dynamic tools. An owned fallback requires explicit selection in the CLI.
- `coc.orchestration`: model tool calls become authenticated, durable child tasks.
- Go broker: principal scopes, idempotency, leases, uncertainty, receipts and audit
  hashes; application callbacks never run inside the broker.
- Host adapters: unrelated Python, Java, JavaScript and Rust applications execute
  their published capabilities. No DRAGONHYDRA module is a dependency.

| Dimension | Reference | COC milestone |
|---|---|---|
| Dependency | DRAGONHYDRA Runtime/Store/UI | Independent broker and SDKs |
| Protocol | Application HTTP plus Codex RPC | COC-PROTOCOL/1 plus documented Codex RPC |
| Identity | Selected thread/workspace, application job | Scoped principal, host, task, parent, thread and receipt |
| Result | Agent-written file, polled | App Server events plus host execution receipts |
| Recovery | Poll retained receipt, reconnect metadata | Durable uncertain state, idempotent reconciliation, explicit Codex resume |
| Portability | One application experiment | Several unrelated demo hosts; not proof of universal compatibility |
| Detachment | Closes client connection | External connection never owns server lifecycle |

Official sources: [Codex App Server](https://developers.openai.com/codex/app-server)
documents Unix WebSocket transport, initialization, thread metadata, turn steering,
resumption and dynamic tools. Dynamic tools remain experimental; TCP WebSocket
transport is additionally described as experimental/unsupported. COC's default
shared local path uses the documented Unix control socket.
