# Application integration

Applications expose deliberate functions, validate inputs and own their effects.
Use an in-process SDK or a sidecar calling an application's supported API. No
private application modules or unrestricted process-memory access are required.

## Python

Install `kernels/python` or the release wheel. A trusted operator issues separate
host and requester credentials. Supply credentials in process-local environment
variables, never shell history or source files.

```python
from coc import Client
from coc.host import HostAdapter, capability

client = Client.from_env()  # COC_URL, COC_TOKEN, COC_AGENT
def count_items(arguments, cancelled, task):
    if cancelled.is_set():
        raise InterruptedError()
    return {"count": len(arguments["items"])}

tools = {"count_items": (capability(
    "count_items", "Count submitted items",
    {"type": "object", "properties": {"items": {"type": "array"}},
     "required": ["items"], "additionalProperties": False},
    {"type": "object", "properties": {"count": {"type": "integer"}},
     "required": ["count"], "additionalProperties": False}), count_items)}
HostAdapter(client, "inventory", "Inventory application", tools).run()
```

The host needs `host:register` and `event:write`. The requester needs
`tool:inventory:count_items`, plus `discover` for discovery. It calls
`client.submit("inventory", "count_items", {"items": [1, 2]}, key="business-id")`
and `client.wait(task["id"])`. Inspect state, result and receipt. Wait timeout
does not cancel an operation. External mutations should persist the COC task ID
in their own transaction/idempotency store.

The common adapter operations are capability discovery, application state, tool
listing, authorized execution, event subscription, task status/cancellation,
error reporting, operator assistance and detachment. Python, Java and TypeScript
provide these methods; Rust exposes lower-level RPC/ABI/host facilities. Independent
heartbeats carry cooperative cancellation. Never replay a non-idempotent effect
solely because the connection failed.

## JavaScript / TypeScript

`sdk/typescript/src/index.ts` exports types, Client, HostAdapter, validation and
events. `npm run build` generates JS and declarations in `sdk/typescript/lib`.
`sdk/javascript/index.mjs` is the JS facade. See the real Node worker under
`examples/javascript-web` and the browser-host tool in the operator panel.

`@cfworker/json-schema` interprets Draft 7 schemas without runtime code generation.
CSP retains same-origin scripts/connections and no unsafe-eval or inline scripts.
Credentials remain in memory; fetch rejects redirects. Browser Web Crypto needs
HTTPS or trustworthy loopback. SSE resumes by sequence with bounded backoff;
credential expiry requires reauthentication.

## Java / Spring

`pwsh scripts/build-java.ps1` produces a JDK 21-compatible JAR. Gson supports
protocol encoding; the enterprise demo additionally uses H2. `io.coc.Client`
provides RPC/discovery/status/cancellation/events, and `HostAdapter` provides
leased execution. `EnterpriseHost` demonstrates durable invoice effects and
synthetic administrative records. Embed the SDK using Spring's normal lifecycle;
no separate Spring Boot starter is claimed. Java's client-side checker covers
the envelope vocabulary; the broker enforces full tool schemas. Its JVM HTTP
transport is not directly Android-compatible.

## Rust / native

`kernels/rust` implements the native SDK. `sdk/rust/coc_native.h` declares the
stable C ABI. `coc_validate_json` accepts valid caller-owned bytes and retains
no pointer; its return code distinguishes valid, invalid and invalid bounds.
The ABI cannot protect a caller supplying an invalid foreign pointer.

`coc-native bridge` provides authenticated NDJSON stdio RPC using COC_URL,
COC_AGENT and COC_TOKEN. `coc-native host` runs the native sum tool.
`coc-native supervise` bounds and terminates its direct child; it does not promise
job-object/process-group containment of arbitrary descendants. Remote calls use
TLS and the same checked-in protocol schema.

## Agent/provider adapters

Provider output becomes scoped child tasks; it cannot directly invoke arbitrary
shell commands. Each provider requires explicit origin, model, credential and
budget configuration. Failed/unknown paid requests retain reservations; no
automatic paid retries occur. Codex supports owned stdio or the existing
current-user control socket, with explicit logical-thread ownership. See the
[live report](../integration/COC-CODEX-LIVE-INTEGRATION.md). Dynamic tool support
is experimental and version-sensitive. Browser/host credentials are distinct
from provider API keys.

The common conformance corpus runs through Python, Java, TypeScript/JS and Rust.
Integration tests execute four host languages against one Go broker; Django reads
real broker state. This demonstrates those supported contracts, not every
application, platform or schema extension.
