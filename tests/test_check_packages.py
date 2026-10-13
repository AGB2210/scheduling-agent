import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "check_packages.py"


def check(pyproject):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(pyproject)], capture_output=True, text=True
    )


def test_the_projects_own_packages_are_all_installed():
    result = check(ROOT / "pyproject.toml")
    assert result.returncode == 0
    assert result.stdout == ""


def test_a_missing_package_is_named(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[project]\n"
        'name = "schedagent"\n'
        'dependencies = ["pydantic>=2.9", "no-such-package-here>=1"]\n'
        "[project.optional-dependencies]\n"
        'dev = ["pytest>=8", "nor-this-one"]\n',
        encoding="utf-8",
    )
    result = check(pyproject)
    assert result.returncode == 1
    assert result.stdout.strip() == "Not installed: no-such-package-here, nor-this-one"
