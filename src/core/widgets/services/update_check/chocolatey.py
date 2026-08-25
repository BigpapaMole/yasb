"""Chocolatey package manager module.

Provides synchronous functions for interacting with Chocolatey:
- check_updates(): List packages with available upgrades
- upgrade_packages(): Upgrade packages in a visible terminal
"""

import logging
import shutil
import subprocess

# Subprocess creation flag to hide the console window.
_CREATE_NO_WINDOW = 0x08000000


def _run_choco(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """Execute a Chocolatey command and return the result."""
    return subprocess.run(
        ["choco", *args],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        shell=True,
        timeout=timeout,
        creationflags=_CREATE_NO_WINDOW,
    )


def check_updates() -> list[dict[str, str]]:
    """Check for available package upgrades via Chocolatey.

    Uses Chocolatey's machine-readable --limit-output format.

    Returns:
        List of dicts with standardized keys:
        ``name``, ``id``, ``version``, ``available``, ``source``.
    """
    try:
        result = _run_choco(
            [
                "outdated",
                "--limit-output",
                "--ignore-pinned",
            ],
            timeout=120,
        )

        # Chocolatey may return exit code 2 when outdated packages exist.
        if result.returncode not in (0, 2):
            logging.error(
                "Chocolatey outdated failed with exit code %s: %s",
                result.returncode,
                result.stderr.strip(),
            )
            return []

        if not result.stdout:
            return []

        updates: list[dict[str, str]] = []

        for line in result.stdout.splitlines():
            line = line.strip()

            if not line:
                continue

            # Chocolatey --limit-output format:
            #
            # packageId|currentVersion|availableVersion|pinned
            #
            parts = line.split("|")

            if len(parts) < 3:
                continue

            package_id = parts[0].strip()
            current_version = parts[1].strip()
            available_version = parts[2].strip()

            if not package_id:
                continue

            updates.append(
                {
                    "name": package_id,
                    "id": package_id,
                    "version": current_version,
                    "available": available_version,
                    "source": "chocolatey",
                }
            )

        return updates

    except subprocess.TimeoutExpired:
        logging.warning("Chocolatey outdated timed out")
        return []

    except FileNotFoundError:
        logging.error("Chocolatey executable not found")
        return []

    except Exception:
        logging.exception("Error checking Chocolatey updates")
        return []


def upgrade_packages(package_ids: list[str]) -> None:
    """Upgrade Chocolatey packages in a visible PowerShell window.

    If package_ids is empty, falls back to ``choco upgrade all -y``.
    """
    powershell = (
        shutil.which("pwsh")
        or shutil.which("powershell")
        or "powershell.exe"
    )

    if package_ids:
        count = len(package_ids)
        package_label = "package" if count == 1 else "packages"

        lines: list[str] = [
            "Write-Host '========================================='",
            f"Write-Host 'YASB found {count} Chocolatey {package_label} ready to update'",
            "Write-Host '========================================='",
        ]

        for package_id in package_ids:
            lines.append(f"Write-Host ' - {package_id}'")

        lines.append("Write-Host ''")

        for package_id in package_ids:
            safe = package_id.replace("'", "''")

            lines.append(
                f"Write-Host '>> Upgrading {safe} ...' -ForegroundColor Cyan"
            )

            lines.append(
                f"choco upgrade '{safe}' -y"
            )

        lines.append("Write-Host ''")
        lines.append(
            "Write-Host 'Chocolatey upgrades complete.' -ForegroundColor Green"
        )
        lines.append(
            "Read-Host 'Press Enter to close'"
        )

        script = "; ".join(lines)

        command = (
            f'start "Chocolatey Upgrade" '
            f'"{powershell}" -NoExit -Command "{script}"'
        )

    else:
        command = (
            f'start "Chocolatey Upgrade" '
            f'"{powershell}" -NoExit -Command "choco upgrade all -y"'
        )

    subprocess.Popen(
        command,
        shell=True,
        creationflags=_CREATE_NO_WINDOW,
    )