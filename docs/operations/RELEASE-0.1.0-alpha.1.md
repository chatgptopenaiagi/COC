# COC 0.1.0-alpha.1

This engineering prerelease connects independently registered applications to
scoped agent tasks through a Go broker with durable SQLite state. All seven
required technologies have executable components and integration evidence.

The operator panel's validator now works under strict CSP without unsafe-eval.
Real browser chat uses an existing Codex App Server with a new application thread
and invokes independent Python and JavaScript hosts. Owned-server mode, bounded
repair, usage accounting and live cancellation also have separate passing tests.
DRAGONHYDRA was treated as a read-only reference, with no runtime dependency.

Windows acceptance: all build stages passed; Go/Rust/Java/JS/TS suites passed;
Python's complete default suite passed 25 tests and deliberately skipped five
live tests. Four separately run live Codex tests passed. Django, MCP, protocol
conformance, browser execution, fault injection and recovery are included.

The archive was independently extracted, hashes checked, Python installed offline
and four packaged hosts executed against its packaged broker. Exact bytes,
checksums and results are in `evidence/releases/latest.json`. Python 3.14 Windows
x64, Java 21+ and Node 22+ are needed for the packaged demonstration runtimes.
Run `COC.ps1 INSTALL`, `START -Demo`, `OPEN`, then `STOP` inside the extraction.

Direct OpenAI authentication/model discovery passed; inference is **BLOCKED** by
HTTP 429 quota/billing and the three-request allowance is exhausted. No retry was
made after the exhausted-budget directive. Local llama.cpp requires a separately
authorized credential. Other optional providers are not live-verified.

Active-turn Codex recovery, Android, production clinical use, distributed HA,
comprehensive OS resource containment and general exactly-once effects are not
claimed. Completed-thread reconnect and bounded local fault scenarios passed.
Linux evidence is reported separately by CI. This is not a production-ready
universal engine; remaining work is tracked in STATUS.md and the roadmap.

The archive excludes credentials, private runtime configuration and databases.
Native binaries are unsigned. API keys must never be used as panel login tokens.
