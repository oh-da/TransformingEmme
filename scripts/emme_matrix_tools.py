"""Shared helpers for turning EMME ``.in`` matrix exports into TAZ-indexed CSVs.

The two pieces of input are:

* ``taz_layer/taz_v41.dbf`` -- the attribute table of ``TAZ_v41.shp``. Its
  ``TAZV41`` column supplies the zone numbering used for the CSV index/header.
* ``Matrices/<scenario>/EMME/*.in`` -- EMME "batchin" matrix files.

EMME batchin format (only the parts we need)::

    t matrices
    d mf99
    c <comment>
    t matrices
    a matrix=mf99   AutoTt   0 sc=11971, Auto total=...
     1101 1105:.031056 1114:.5
     1101 1118:.031056 1120:.031056
     ...

Everything before the ``a matrix=`` line is header/metadata. Each data line is
an origin zone followed by ``destination:value`` pairs. A line that starts
directly with a pair continues the previous origin (allowed by the format, so
it is handled even though the exports at hand always repeat the origin).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# Matrix families exported per scenario and the period suffix of each file.
MATRIX_KINDS = ("AUTOTOT", "PRKRTotDemand", "TransitTotDemand")
PERIODS = {"a": "AM", "o": "Offpeak", "p": "PM"}

# Human readable labels for the matrix families.
KIND_LABELS = {
    "AUTOTOT": "Auto total trips",
    "PRKRTotDemand": "Park & Ride + Kiss & Ride total demand",
    "TransitTotDemand": "Transit total trips",
}

# Scenario directories whose name differs from the scenario's name. The 2050
# Strategic Plan scenario (5972) is stored in a directory called ``2050_HS``
# but is referred to as 2050_SP everywhere else.
SCENARIO_LABELS = {"2050_HS": "2050_SP"}

# EMME scenario numbers, from ExportedMatrices_TLVModel_V433.txt.
SCENARIO_NUMBERS = {"2018": 1971, "2050_BU": 5971, "2050_SP": 5972}


def scenario_label(directory_name: str) -> str:
    """Scenario name to report for a directory under ``Matrices``."""
    return SCENARIO_LABELS.get(directory_name, directory_name)


def matches_scenario(directory_name: str, wanted: str) -> bool:
    """True if ``wanted`` names this scenario, by directory name or by label."""
    return wanted in (directory_name, scenario_label(directory_name))


# --------------------------------------------------------------------------- #
# TAZ layer
# --------------------------------------------------------------------------- #
def read_dbf_column(dbf_path: Path, column: str) -> list:
    """Read a single column out of a dBase III (.dbf) table.

    Implemented directly against the file format so the conversion has no
    GIS dependency (geopandas/pyshp are not needed just to read attributes).
    """
    with open(dbf_path, "rb") as fh:
        _ver, _y, _m, _d, n_records, header_len, record_len = struct.unpack(
            "<BBBBIHH", fh.read(12)
        )
        fh.seek(32)

        fields = []  # (name, type, length, offset)
        offset = 0
        while True:
            descriptor = fh.read(32)
            if descriptor[:1] in (b"\r", b"", b"\x1a"):
                break
            name = descriptor[0:11].split(b"\x00")[0].decode("latin-1")
            ftype = descriptor[11:12].decode("latin-1")
            flen = descriptor[16]
            fields.append((name, ftype, flen, offset))
            offset += flen

        match = [f for f in fields if f[0] == column]
        if not match:
            raise KeyError(
                f"column {column!r} not found in {dbf_path.name}; "
                f"available: {[f[0] for f in fields]}"
            )
        _name, ftype, flen, foff = match[0]

        fh.seek(header_len)
        values = []
        for _ in range(n_records):
            record = fh.read(record_len)
            if len(record) < record_len:
                break
            if record[:1] == b"*":  # deleted record
                continue
            raw = record[1 + foff : 1 + foff + flen].decode("latin-1").strip()
            if ftype == "N":
                values.append(int(raw) if raw else None)
            elif ftype == "F":
                values.append(float(raw) if raw else None)
            else:
                values.append(raw)
        return values


def read_taz_ids(dbf_path: Path, column: str = "TAZV41") -> np.ndarray:
    """Return the sorted, unique TAZ ids that index the output matrices."""
    values = [v for v in read_dbf_column(dbf_path, column) if v is not None]
    unique = sorted(set(values))
    if len(unique) != len(values):
        raise ValueError(
            f"{column} is not unique in {dbf_path.name}: "
            f"{len(values)} rows, {len(unique)} distinct values"
        )
    return np.asarray(unique, dtype=np.int64)


# --------------------------------------------------------------------------- #
# EMME .in parsing
# --------------------------------------------------------------------------- #
@dataclass
class ParsedMatrix:
    """A parsed ``.in`` file plus the bookkeeping needed for the QA tests."""

    path: Path
    matrix_header: str
    matrix: np.ndarray  # len(taz_ids) x len(taz_ids), TAZ-to-TAZ trips
    taz_ids: np.ndarray

    file_total: float = 0.0  # sum of every value in the file
    taz_total: float = 0.0  # sum of the values that land inside the matrix
    n_pairs: int = 0  # origin/destination pairs read from the file
    n_pairs_in_taz: int = 0
    duplicate_pairs: int = 0  # O-D pairs listed more than once
    negative_values: int = 0
    off_taz_origins: set = field(default_factory=set)
    off_taz_dests: set = field(default_factory=set)
    off_taz_total: float = 0.0
    # zone id -> trips leaving / arriving, for the zones that are not in TAZV41
    off_taz_from: dict = field(default_factory=dict)
    off_taz_to: dict = field(default_factory=dict)

    @property
    def n_zones(self) -> int:
        return len(self.taz_ids)


def parse_emme_in(path: Path, taz_ids: np.ndarray) -> ParsedMatrix:
    """Parse an EMME ``.in`` matrix export into a dense TAZ x TAZ array."""
    index = {int(z): i for i, z in enumerate(taz_ids)}
    n = len(taz_ids)
    matrix = np.zeros((n, n), dtype=np.float64)
    seen = set()

    result = ParsedMatrix(
        path=path, matrix_header="", matrix=matrix, taz_ids=taz_ids
    )

    started = False
    origin_id = None
    origin_pos = None

    with open(path, "r", encoding="latin-1") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not started:
                if line.startswith("a matrix="):
                    started = True
                    result.matrix_header = line.rstrip("\n").strip()
                continue

            stripped = line.strip()
            if not stripped:
                continue
            # A second block header would mean more than one matrix per file,
            # which these exports do not use -- fail loudly rather than merge.
            if stripped.startswith("a matrix="):
                raise ValueError(
                    f"{path}: more than one matrix block (line {lineno})"
                )
            if stripped[0] in "tdc" and (len(stripped) == 1 or stripped[1] == " "):
                continue

            tokens = stripped.split()
            if ":" not in tokens[0]:
                origin_id = int(tokens[0])
                origin_pos = index.get(origin_id)
                tokens = tokens[1:]
            elif origin_id is None:
                raise ValueError(
                    f"{path}: destination pair before any origin (line {lineno})"
                )

            for token in tokens:
                dest_text, _, value_text = token.partition(":")
                dest_id = int(dest_text)
                value = float(value_text)

                result.n_pairs += 1
                result.file_total += value
                if value < 0:
                    result.negative_values += 1

                dest_pos = index.get(dest_id)
                if origin_pos is None or dest_pos is None:
                    if origin_pos is None:
                        result.off_taz_origins.add(origin_id)
                        result.off_taz_from[origin_id] = (
                            result.off_taz_from.get(origin_id, 0.0) + value
                        )
                    if dest_pos is None:
                        result.off_taz_dests.add(dest_id)
                        result.off_taz_to[dest_id] = (
                            result.off_taz_to.get(dest_id, 0.0) + value
                        )
                    result.off_taz_total += value
                    continue

                key = (origin_pos, dest_pos)
                if key in seen:
                    result.duplicate_pairs += 1
                else:
                    seen.add(key)
                matrix[origin_pos, dest_pos] += value
                result.taz_total += value
                result.n_pairs_in_taz += 1

    if not started:
        raise ValueError(f"{path}: no 'a matrix=' block found")
    return result


# --------------------------------------------------------------------------- #
# CSV output
# --------------------------------------------------------------------------- #
def write_matrix_csv(
    matrix: np.ndarray, taz_ids: np.ndarray, out_path: Path, fmt: str = "%.9g"
) -> None:
    """Write a square matrix as CSV with TAZ ids as both index and header.

    The first column is the origin TAZ (``TAZV41``), the header row lists the
    destination TAZs. ``%.9g`` keeps every digit present in the ``.in`` files
    while printing exact zeros as ``0``.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ids = [str(int(z)) for z in taz_ids]
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        fh.write("TAZV41," + ",".join(ids) + "\n")
        for i, zone in enumerate(ids):
            row = matrix[i]
            fh.write(zone + "," + ",".join([fmt % v for v in row]) + "\n")


def read_matrix_csv(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read back a CSV written by :func:`write_matrix_csv`.

    Returns ``(row_ids, col_ids, matrix)``.
    """
    with open(path, "r", encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split(",")
        col_ids = np.asarray([int(c) for c in header[1:]], dtype=np.int64)
        rows = []
        row_ids = []
        for line in fh:
            if not line.strip():
                continue
            parts = line.rstrip("\n").split(",")
            row_ids.append(int(parts[0]))
            rows.append(np.asarray(parts[1:], dtype=np.float64))
    return np.asarray(row_ids, dtype=np.int64), col_ids, np.vstack(rows)


# --------------------------------------------------------------------------- #
# Layout helpers
# --------------------------------------------------------------------------- #
def find_scenarios(matrices_root: Path) -> list[Path]:
    """Scenario directories are the children of ``Matrices`` holding an EMME dir."""
    return sorted(p for p in matrices_root.iterdir() if (p / "EMME").is_dir())


def expected_files(scenario_dir: Path) -> list[tuple[str, str, Path]]:
    """Yield ``(kind, period, path)`` for the 9 matrices of one scenario."""
    out = []
    for kind in MATRIX_KINDS:
        for period in PERIODS:
            out.append((kind, period, scenario_dir / "EMME" / f"{kind}_{period}.in"))
    return out
