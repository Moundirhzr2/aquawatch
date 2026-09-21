# Windows setup and validation

Docker Desktop 4.90.0 and WSL 2.7.13.0 were installed on the build machine. Hardware virtualization is enabled. The user completed the required Windows restart, and the full container integration check passed on 2026-09-13. No further restart is required for this completed setup.

## Reproduce the container check

1. Open Docker Desktop and wait until its Linux engine is running.
2. Open a fresh PowerShell window in the repository and activate the Python environment.
3. Run `docker info` to confirm that the server is available, then run:

```powershell
python scripts/check_containers.py
```

If Docker is not yet on your PATH, add its installed directory for the current
PowerShell session. For the verified per-user installation:

```powershell
$env:PATH = "$env:LOCALAPPDATA/Programs/DockerDesktop/resources/bin;$env:PATH"
docker --version
python scripts/check_containers.py
```

Use only a trusted Docker installation directory. The checker always invokes
`docker`; it does not accept executable paths or additional commands through CLI
arguments. The former `--docker` option has been removed.

The check builds and starts a disposable Compose project. It uses distinct available ports so a running AquaWatch instance can stay open. Its database and reporting exports are temporary, and it removes its own containers and volumes when finished. The image remains in Docker's build cache. Initial image downloads require an internet connection.

On a new Windows installation, Docker may require the WSL and Virtual Machine Platform optional features and a restart before its engine can start. On the tested machine, these components are now active and the integration script completed successfully. See the [validation record](validation.md) for the exact checks.

For reference, consult the official [Docker Windows installation guide](https://docs.docker.com/desktop/setup/install/windows-install/) and [Microsoft WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install).

## Inspect the Power BI report

Power BI Desktop is installed. Set the local CSV folder before opening the report, as described in the [Power BI README](../powerbi/README.md). Refresh all tables, inspect all three report pages and check their totals against the CSV exports and [metric definitions](metric-definitions.md).

The Windows inspection tool repeatedly failed with `SetIsBorderRequired ... 0x80004002` and returned no readable report controls. Native Power Query refresh, DAX evaluation and filter behavior have now passed through the local model engine. User screenshots confirm PBIP opening, Desktop refresh and all three populated pages. The updated formatting on all three pages is also confirmed, including exact card totals and readable table headers. The user manually confirmed that Billing review district selections update the linked visuals. See [Power BI validation](powerbi-validation.md) for reproducible native checks and expected visual totals.
