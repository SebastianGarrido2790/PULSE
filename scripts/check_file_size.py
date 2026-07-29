"""Fail if any tracked Python source file in src/ exceeds the line-count ceiling.

Run via `python scripts/check_file_size.py`. Exits non-zero — and prints every
offending file — if any file is over the limit, unless explicitly allowlisted.

The allowlist exists for rare, justified exceptions (e.g., an auto-generated
schema file) and must carry a one-line reason next to each entry. It is not a
place to quietly park a file that should be split.
"""

from pathlib import Path

LINE_LIMIT = 1_000
SRC_ROOT = Path("src")

# Explicit, reviewed exceptions only. Each entry must carry a reason.
ALLOWLIST: dict[str, str] = {
    # "src/schemas/point_record.py": "auto-generated from an upstream OpenAPI spec",
}


def main() -> int:
    """Check every .py file under src/ against the line-count ceiling.

    Returns:
        0 if all files pass (or are allowlisted), 1 if any file violates
        the ceiling without an allowlist entry.
    """
    violations: list[tuple[str, int]] = []

    for path in SRC_ROOT.rglob("*.py"):
        rel_path = str(path)
        line_count = sum(1 for _ in path.open(encoding="utf-8"))

        if line_count > LINE_LIMIT and rel_path not in ALLOWLIST:
            violations.append((rel_path, line_count))

    if violations:
        print(f"File size ceiling ({LINE_LIMIT} lines) violated:\n")
        for rel_path, line_count in violations:
            print(f"  {rel_path}: {line_count} lines")
        print("\nSplit the file along an existing responsibility boundary, "
              "or add a justified entry to ALLOWLIST in this script.")
        return 1

    print(f"All src/ files are within the {LINE_LIMIT}-line ceiling.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
