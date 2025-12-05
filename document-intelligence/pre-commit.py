#!/usr/bin/env python3
"""Pre-commit checks script."""

import argparse
import subprocess
import sys


def run_check(name: str, command: list[str]) -> bool:
    """Run a check command and return True if it passes."""
    print(f"\n{'=' * 60}")
    print(f"Running: {name}")
    print(f"Command: {' '.join(command)}")
    print("=" * 60)

    try:
        result = subprocess.run(command, check=False, capture_output=False, text=True)

        if result.returncode == 0:
            print(f"✓ {name} passed")
            return True
        else:
            print(f"✗ {name} failed with exit code {result.returncode}")
            return False

    except Exception as e:
        print(f"✗ {name} failed with error: {e}")
        return False


def main():
    """Run all pre-commit checks."""
    parser = argparse.ArgumentParser(description="Run pre-commit checks")
    parser.add_argument(
        "--fix", action="store_true", help="Auto-fix issues with ruff check --fix and ruff format"
    )
    args = parser.parse_args()

    mode = "fix mode" if args.fix else "check mode"
    print(f"Starting pre-commit checks ({mode})...")

    if args.fix:
        checks = [
            ("ruff check --fix", ["uv", "run", "ruff", "check", "--fix", "."]),
            ("ruff format", ["uv", "run", "ruff", "format", "."]),
        ]
    else:
        checks = [
            ("ruff check", ["uv", "run", "ruff", "check", "."]),
            ("ruff format --check", ["uv", "run", "ruff", "format", "--check", "."]),
            ("pyright", ["uv", "run", "pyright"]),
            ("pytest", ["uv", "run", "pytest"]),
        ]

    results = []
    for name, command in checks:
        passed = run_check(name, command)
        if not passed:
            sys.exit(1)

        results.append((name, passed))

    # Summary
    print(f"\n{'=' * 60}")
    print("Summary:")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 All checks passed!")
        sys.exit(0)
    else:
        print("\n❌ Some checks failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
