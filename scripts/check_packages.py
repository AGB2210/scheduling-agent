"""Check that every package named in pyproject.toml is installed.

start.bat runs this each time and installs the packages when it fails. It
looks at names only, not version numbers.
"""

import re
import sys
import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def missing_packages(pyproject: Path) -> list[str]:
    project = tomllib.loads(pyproject.read_text("utf-8"))["project"]
    wanted = [project["name"], *project.get("dependencies", [])]
    for extra in project.get("optional-dependencies", {}).values():
        wanted += extra
    missing = []
    for requirement in wanted:
        # "pydantic>=2.9" names the package pydantic.
        name = re.match(r"[A-Za-z0-9._-]+", requirement)[0]
        try:
            version(name)
        except PackageNotFoundError:
            missing.append(name)
    return missing


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "pyproject.toml")
    missing = missing_packages(path)
    if missing:
        print("Not installed: " + ", ".join(missing))
        sys.exit(1)
