# Security model

The initial trust boundary is the OS user, the broker credential and the host
capability manifest. A host is trusted to implement its own advertised tools; a
model's assertion is untrusted. Tool access requires exact `tool:host:operation`
scopes. Child grants cannot widen authority. Token expiry and ancestor revocation
are checked on every request, including ongoing event streams.

Broker tokens are random and stored as hashes in SQLite. The local controller
protects its generated bootstrap credential with Windows DPAPI and a current-user
ACL. Unix fallback uses owner-only directories/files. These controls do not
protect against the same user or an administrator inspecting process memory.
For stronger assurance use separate OS identities, credential managers, remote
TLS with managed certificates and an independently governed approval service.

`openai-api-key.txt` is an explicitly authorized, existing private input. COC reads
it only for configured provider requests or in-memory publication comparisons;
it never copies it to evidence, packages or source control. `.runtime`, key files,
databases and private configuration are excluded from Git and packaging. Run
`scripts/scan-secrets.py` before every commit/publication. Never supply provider
keys to the browser or to a different service's endpoint.

Remote broker connections require HTTPS. Local HTTP is restricted to loopback.
SDK credential-bearing requests reject redirects. The operator panel uses a
same-origin CSP without `unsafe-eval` or inline scripts. Its validator executes no
generated code. One-use login codes expire in 60 seconds and are exchanged once;
they are removed from browser history before the exchange. The resulting
credential stays only in page memory. SSE credentials are never query parameters.

Codex socket access is authorized by OS permissions and explicit workspace/thread
selection. An attached connector closes only its connection. No process-memory
inspection, terminal injection, credential scraping or broad approval forwarding
is implemented. Dynamic tool requests are constrained by the host allowlist and
broker scope. Unexpected approval requests are declined. A read-only sandbox is
not a guarantee of protection from the same-user administrator; use separate
accounts/containers for untrusted code or sensitive data.

Provider request limits persist before network transmission. Unknown outcomes
consume their reservations and are not automatically retried. Configured monetary
ceilings require explicit prices; token/byte estimates are not billing invoices.
Codex usage updates can lag execution, so its token stop is a cooperative bound,
not an exact hard cap on remote billing. A cancellation acknowledgement also does
not prove a remote provider stopped charging immediately.

Clinical demonstrations contain synthetic records only. No medication, diagnosis,
patient-record update or clinical deployment tool exists. Production deployment,
independent security assessment, data retention policies, audit signatures,
regulated-system certification and high-assurance credential isolation remain
outside this alpha's verified scope.
