"""Guards for the operator-facing PowerShell setup scripts.

These run on any platform: they are text checks, not PowerShell invocations, so
CI (ubuntu) enforces the same rule the Windows operator path depends on.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL_SCRIPTS = sorted((ROOT / "scripts").glob("*.ps1"))

# "$name:" inside a double-quoted string is parsed by PowerShell as a scoped
# variable reference (as in $env:PATH). When the colon is not followed by a valid
# variable name character the whole file fails to parse, so the script is dead on
# arrival rather than failing only on the affected branch. ${name}: is the safe form.
_SCOPED_INTERPOLATION = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*:")

# Legitimate PowerShell scopes/drives, which are genuinely meant to be written $scope:name.
_ALLOWED_SCOPES = frozenset(
    {"env", "script", "global", "local", "private", "using", "variable", "function"}
)


def test_operator_powershell_scripts_exist() -> None:
    assert POWERSHELL_SCRIPTS, "expected at least one operator PowerShell script"


def test_no_unbraced_scoped_variable_interpolation() -> None:
    offenders: list[str] = []
    for script in POWERSHELL_SCRIPTS:
        for number, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
            for match in _SCOPED_INTERPOLATION.finditer(line):
                scope = match.group(0)[1:-1]
                if scope.lower() in _ALLOWED_SCOPES:
                    continue
                offenders.append(
                    f"{script.relative_to(ROOT).as_posix()}:{number}: {match.group(0)} "
                    f"-- use ${{{scope}}}: instead"
                )
    assert not offenders, "PowerShell scoped-variable interpolation would fail to parse:\n" + "\n".join(
        offenders
    )
