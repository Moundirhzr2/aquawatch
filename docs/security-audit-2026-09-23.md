# Security review — 23 September 2026

## Scope and evidence

This review covers the source, locked Python and npm dependencies, tracked files, Compose configuration, the final application image from [CI run 35802174971](https://github.com/Moundirhzr2/aquawatch/actions/runs/35802174971), and the local application/browser tests. AquaWatch remains a loopback-only, single-operator synthetic-data demonstration, not a production multi-user service.

| Check | Result |
| --- | --- |
| Python tests, lint, installed dependency consistency | 33 passed; Ruff and `pip check` passed. Two upstream test-client deprecation warnings remain. |
| Browser workflow | Passed in an isolated Chrome run, including responsive layout, case decisions, import replay and no JavaScript errors. |
| OSV locked dependency query | 84 PyPI/npm versions queried; no matching published advisories at the time of the query. This is a point-in-time result. |
| Tracked-file secret and release scan | 153 candidate files checked; no matching known local credentials, common token signatures, private paths or runtime files. Signature matching is not exhaustive. |
| Bandit static analysis | 40 findings: 30 low-severity assertions in validation scripts, eight low-severity subprocess import/call warnings for fixed executables and argument arrays, one low-severity deterministic fixture RNG warning, and one medium-severity SQL-string warning. The SQL identifiers come only from the fixed `MARTS` list and the target is selected by project code; no request input reaches the query identifier. No confirmed injection path was found. |
| GitHub security signals | [SonarCloud](https://github.com/Moundirhzr2/aquawatch/runs/106994861189) and [Semgrep](https://github.com/Moundirhzr2/aquawatch/runs/106994860538) passed on the reviewed commit; the accessible secret-scanning API reported zero open alerts. Dependabot alerts returned HTTP 403 and GitHub code-scanning alerts HTTP 404 to the available credential, so their absence cannot be claimed. |
| Docker Compose | `docker compose config --quiet` passed with a non-secret placeholder password. The local Docker engine did not answer `docker info` within 20 seconds, so no local image scan is claimed. The CI image scan below is the current image evidence. |

## Container findings that remain open

The final-image Trivy report from the CI `containers` job has **156 package findings: 44 high, 49 medium, 57 low and 6 unknown; no critical findings**. These are package/advisory entries, not 156 distinct CVEs. The 44 high entries map to **eight distinct CVEs**: `CVE-2025-69720`, `CVE-2026-16742`, `CVE-2026-54369`, `CVE-2026-76642`, `CVE-2026-78408`, `CVE-2026-78409`, `CVE-2026-78410`, and `CVE-2026-9538`. Trivy reported **no fixable finding** for this image at scan time, and its Python-package section had zero findings. The required CI gate checks fixable high/critical issues, so a green gate does not mean that the image has no CVEs.

The Debian tracker still marks Trixie vulnerable for, among others, [util-linux CVE-2026-76642](https://security-tracker.debian.org/tracker/CVE-2026-76642), [ncurses CVE-2025-69720](https://security-tracker.debian.org/tracker/CVE-2025-69720), [Perl CVE-2026-9538](https://security-tracker.debian.org/tracker/CVE-2026-9538) and [libacl CVE-2026-54369](https://security-tracker.debian.org/tracker/CVE-2026-54369). Several described exploit paths require privileged host tools, local users or features not exercised by this non-root application container. That limits likely exposure in the documented local demo; it does not make the affected packages or scanner results false. Do not publish the API or load real customer data on the basis of this assessment.

## Changes and priorities

This review fixes the import button's loading-label regression introduced when its icon became the first child span. A browser regression assertion now verifies that the icon remains unchanged after import. The Compose app and analytics services also drop Linux capabilities and prohibit privilege escalation; the PostgreSQL service is unchanged because its entrypoint may need startup privileges. CI container integration must validate these settings before merge.

Next priorities:

1. Rebuild with `docker build --pull --no-cache`, inspect the full Trivy artifact, and recheck Debian Trixie fixes as they are released. Test any base-image change before adopting it.
2. Include the `postgres:17` image in the automated vulnerability inventory and pin/review its digest for reproducibility.
3. Before any public or real-data deployment, add authenticated users and roles, TLS, rate limits, backup and recovery, migration and retention policies, and database least-privilege roles. The current `/api/session` write token is cross-origin protection, not identity authentication.

The checks above are evidence for the local demo and a prioritized maintenance list, not a certification or guarantee that undiscovered vulnerabilities are absent.
