# Synthetic healthcare demonstration

The Java enterprise host exposes `synthetic_report`, a read-only administrative
example generated entirely from synthetic constants. It uses a FHIR-shaped Bundle
and Patient structure with an explicit synthetic marker. This is not a conformant
FHIR server, validated implementation guide, laboratory interface or clinical
system certification. The extra demo marker is not a standard FHIR field.

FHIR defines structured exchange/content models; it does not itself supply
authentication or authorization. Production deployments need independent identity,
access control, secure transport and audit mechanisms. See the official
[FHIR security specification](https://hl7.org/fhir/security.html).

COC tests only the synthetic administrative export and application diagnostics.
Real records are not imported or automatically sent to providers. No medication,
diagnosis, clinical record update or clinical deployment capability is published.
An actual hospital integration would need a separately reviewed adapter, explicit
data minimization, purpose/role controls, local redaction and institutional
authorization. COC engineering credentials do not confer clinical authority.

The repair lab is separate: it modifies an isolated synthetic arithmetic report,
passes an independent oracle and prepares evidence. It does not deploy changes.
Qualified application owners retain deployment and rollback decisions.
