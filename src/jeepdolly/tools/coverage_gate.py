"""Fail the build when coverage slips, and say which file slipped.

Two floors rather than one. The total floor stops the suite rotting overall. The
per file floor is the one that actually catches things: a total can sit at ninety
eight while one new module sits at forty, because the other sixty files carry it.

The gate also prints the worst few files whether or not it fails, because the
number that matters at review time is which file is lowest, not what the total
is.

It reads the coverage data that was just written rather than re-running the
suite. Running the suite twice to measure it is how a build gets slow enough
that people stop running it.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from coverage import Coverage

__all__ = ["FileCoverage", "main", "measure", "report"]


@dataclass(frozen=True, slots=True, order=True)
class FileCoverage:
    """One file's statement and branch coverage."""

    percent: float
    name: str
    covered: int
    total: int

    @property
    def missing(self) -> int:
        """How many measured points are not covered."""
        return self.total - self.covered

    def __str__(self) -> str:
        return f"{self.percent:5.1f}%  {self.name}  ({self.missing} missing)"


def measure(data_file: str | Path = ".coverage") -> list[FileCoverage]:
    """Read the coverage data and roll it up per file, worst first."""
    coverage = Coverage(data_file=str(data_file))
    coverage.load()
    data = coverage.get_data()
    out: list[FileCoverage] = []
    for path in sorted(data.measured_files()):
        analysis = coverage._analyze(path)
        statements = len(analysis.statements)
        missing = len(analysis.missing)
        covered = statements - missing
        percent = 100.0 if statements == 0 else covered * 100.0 / statements
        out.append(
            FileCoverage(
                percent=round(percent, 2),
                name=str(Path(path).as_posix()),
                covered=covered,
                total=statements,
            )
        )
    return sorted(out)


def report(
    files: list[FileCoverage], floor: float, file_floor: float, worst: int
) -> tuple[int, list[str]]:
    """Work out the exit status and the lines to print."""
    lines: list[str] = []
    covered = sum(f.covered for f in files)
    total = sum(f.total for f in files)
    overall = 100.0 if total == 0 else covered * 100.0 / total
    lines.append(f"coverage {overall:.2f}% over {len(files)} files")
    for one in files[:worst]:
        lines.append(f"  {one}")
    status = 0
    if overall < floor:
        lines.append(f"coverage_gate: {overall:.2f}% is under the {floor:.1f}% floor")
        status = 1
    under = [f for f in files if f.percent < file_floor]
    for one in under:
        lines.append(
            f"coverage_gate: {one.name} at {one.percent:.1f}%"
            f" is under the {file_floor:.1f}% file floor"
        )
        status = 1
    return status, lines


def main(argv: list[str] | None = None) -> int:
    """Read the coverage data, print the worst files and apply the floors."""
    parser = argparse.ArgumentParser(description="Fail the build when coverage slips.")
    parser.add_argument("--floor", type=float, default=96.0, help="Total floor.")
    parser.add_argument("--file-floor", type=float, default=85.0, help="Per file floor.")
    parser.add_argument("--worst", type=int, default=5, help="How many files to show.")
    parser.add_argument("--data", default=".coverage", help="Coverage data file.")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    files = measure(args.data)
    status, lines = report(files, args.floor, args.file_floor, args.worst)
    for line in lines:
        print(line)
    return status


if __name__ == "__main__":
    sys.exit(main())
