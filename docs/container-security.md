# Container security

The Docker image retains Python 3.12 and explicitly selects Debian 13 (trixie).
Its base digest is pinned; installed Debian packages are upgraded during the build.
Rebuild with `docker build --pull --no-cache -t aquawatch .` to refresh security
updates instead of reusing an old cached package-upgrade layer.

## Snyk PR #9

The automated proposal selected Python 3.15.0rc1 on Debian 12. This changed both
the validated Python version and distribution while retaining known issues.
The revised fix keeps Python 3.12 and applies Debian's published security fixes:

| Component | Findings | Minimum Debian 13 package version |
| --- | --- | --- |
| `perl-base` | CVE-2026-8376, CVE-2026-42496, CVE-2026-13221 | `5.40.1-6+deb13u1` |
| `libpcre2-8-0` | CVE-2026-89161, CVE-2026-89157 | `10.46-1~deb13u2` |

The image build fails if either minimum is not met. Sources:
[Debian Perl tracker](https://security-tracker.debian.org/tracker/CVE-2026-8376),
[archive extraction issue](https://security-tracker.debian.org/tracker/CVE-2026-42496),
[Perl integer truncation](https://security-tracker.debian.org/tracker/CVE-2026-13221),
[PCRE2 invalid free](https://security-tracker.debian.org/tracker/CVE-2026-89161),
[PCRE2 overflow](https://security-tracker.debian.org/tracker/CVE-2026-89157).

## Verification and remaining findings

The required `containers` CI job runs the application integration tests, builds
the final image, records package versions and scans that image with Trivy. It
blocks fixable high/critical vulnerabilities. The `container-security-report`
artifact includes all severities and unfixed issues, so remaining findings are
visible rather than suppressed. A passing gate is not a claim of zero CVEs.

The initial final-image scan also found six fixable pip findings inherited from
the base image. The Docker build upgrades pip to the verified Python-3.12-compatible
release `26.2.1` before installing the locked application dependencies.
Downloaded dependencies must be binary wheels. The dbt experimental parser's
PyPI release contains only a downloader source archive. `requirements-container.txt`
references the official Linux x86_64/aarch64 wheels directly, with SHA-256 values
from that release's `assets.json`; its version remains constrained by
`requirements.lock`. This avoids running the downloader build backend. When
updating the parser, update both its lock entry and these verified wheel references.
Once installation completes, pip
is uninstalled from the runtime image: its vendored msgpack 1.1.2 and setuptools
70.3.0 still have published fixes, even though the application uses newer locked
dependencies. Removing the unused installer removes those copies rather than
suppressing their findings. Container integration exercises the API and dbt
without pip installed.

Snyk's GitHub Dockerfile project analyzes the referenced base image; it may still
report packages fixed by a later `RUN apt-get upgrade` layer. Compare that report
with the final-image scan and recorded package versions. Do not ignore an issue
solely because application tests pass. Upstream issues without a released fix
remain under review; rebuild and rescan when updates become available.
