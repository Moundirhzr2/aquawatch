# Security and deployment scope

AquaWatch is a **local, single-operator synthetic-data demonstration**. Do not expose it publicly or import actual customer records without a separate security and data-governance design.

Implemented controls:

- Loopback binding by default; Compose publishes ports only on `127.0.0.1`.
- Trusted host allowlist, no permissive cross-origin policy, per-process write token.
- Database-backed state, parameterized SQLAlchemy expressions, allowlisted reporting table identifiers.
- HTML escaping of dynamic UI content and CSV formula-prefix handling on case export.
- Bounded upload content, canonical date/numeric validation, quarantine, database uniqueness and foreign keys.
- Optimistic case revisions and transactional audit entries.
- Random local Compose credentials generated into ignored `.env`; no credentials in report source.

Limitations:

- The session endpoint returns a write token to any local reader. This is browser cross-origin protection, **not user authentication**.
- The recorded actor is a local demo label, not verified identity.
- Quarantined payloads are retained. No sensitive-data redaction or automated retention is implemented.
- Use one API worker and one ingestion writer. Do not run parallel external CLI imports.
- Database schema creation supports fresh installs; migrations for established deployments are not included.
- Failed/running file hashes are not automatically retried or recovered.
- The HTML API documentation loads Swagger/Redoc assets from jsDelivr; the main application works without third-party browser assets.

Before production: authenticated users/roles, TLS, private networking, per-source job locks, recoverable jobs, migrations, backups, retention/redaction, request-rate limits, database least-privilege roles, dependency scanning and independent domain validation.

If reporting an issue, use synthetic reproduction data and never include credentials or real customer records in a public issue.
