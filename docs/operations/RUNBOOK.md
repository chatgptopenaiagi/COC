# Operator runbook

## Installation

Source development requires PowerShell 7, Python 3.12+, Go 1.26+, Rust with native
link tools, JDK 21+ and Node 22+. Run `./COC.ps1 INSTALL`, then `VERIFY`.
Release archives include broker/native binaries, Python wheel/dependencies,
Java JAR/dependencies and compiled UI. Python, Java and Node remain external
runtimes. The bundled offline wheelhouse targets **CPython 3.14 Windows x64**.

Extract into an independent directory, verify archive SHA-256 and manifest, then
run `./COC.ps1 INSTALL` to install the packaged Python runtime offline. This does
not install development toolchains, change global environment variables or
install an OS service. Use source-checkout installation for development.

`START -Demo` runs a broker and four actual host workers. Add `-Codex` to connect
a COC Python worker to an available existing Codex endpoint. It owns its Python
process, not the external Codex server. `OPEN` opens a single-use 60-second panel
login code. Credentials remain in browser memory. Never share that URL.

`STATUS` reports actual state. Default broker port is 7310; `-Port 0` selects an
available port. `STOP` shuts down only COC-recorded processes matching PID,
executable and creation time. The database stays under `.runtime/installation`.

## Credentials and recovery

Windows controller secrets use current-user DPAPI and restricted directory ACLs.
POSIX uses 0700/0600 directory/file modes. The broker stores credential hashes,
scopes, expiration and parent relationships. Revoking an ancestor invalidates
descendants. Child-process environment credentials remain sensitive OS data.

Bootstrap credentials last 30 days, demo grants 24 hours, panel tokens one hour.
This alpha does not silently renew them or implement automated bootstrap rotation.
Preserve the database and perform authorized reprovisioning when needed; never
delete task history as an authentication fix. Protect stopped-broker backups.

`RECOVER` lists uncertain tasks and never blindly retries. Inspect committed
host state first. Only declared idempotent tools can use the initial retry policy.
Active Codex-turn reconnection is unverified; completed-thread reconnect is
verified. Restart exited hosts when needed: Python retries connectivity, whereas
native/Java/JS process failures may need operator restart. There is no general
exactly-once or automatic failover guarantee.

## Optional Django

Install Django in the isolated environment. Set COC_DJANGO_SECRET from a private
secret store, configure COC_URL/COC_AGENT/COC_TOKEN for the dashboard's authority,
and set COC_ADMIN_DB to a private path. Use `frameworks/django/manage.py migrate`
and `createsuperuser`; no default password exists. The development server is for
local work; remote use needs supervised WSGI and TLS configuration.

Staff authentication and CSRF gate the dashboard. Viewing requires `system:read`;
controls also require the Django control permission and broker task authority.
Do not give the dashboard provider API keys. Administrative notes/configuration
are separate from the broker's authoritative task storage.

## Verification and packaging

`VERIFY` builds all mandatory components, runs default suites, scans publication
files and summarizes evidence. Nonzero failures stop execution. Five opt-in live
tests are skipped by default and their earlier live evidence is reported separately.
Stop the local demo runtime before BUILD/TEST/VERIFY on Windows: the running JVM
holds its JAR open, so a rebuild cannot replace it. STOP preserves recorded tasks
and does not terminate the independently owned Codex App Server.
`PACKAGE` requires passing local acceptance and creates checksums and a manifest.
`scripts/verify-package.py` verifies bytes, installs offline in a fresh extraction
and executes four host languages against the packaged broker. Keep its release
receipt. Binaries are unsigned engineering prereleases, not clinical software.

The direct OpenAI allowance is exhausted: three HTTP 429 requests, quota/billing.
Authentication/model discovery passed; inference did not. No automatic retry,
credential switch or ledger reset is permitted. New explicit test-budget approval
is required. The existing local inference service also needs its own authorized
credential. No duplicate model downloads were made.

This single-machine broker is not a distributed HA scheduler. Some snapshots and
admission checks scan history; indexing, pagination, retention and global quotas
need further work. Events are not automatically purged. Scoped memory supports
TTL. OS resource isolation and remote-provider hard billing limits are incomplete.
Metrics label their scope; unavailable GPU measurements remain unavailable.
