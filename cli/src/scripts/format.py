#!/usr/bin/env python3
import os
import subprocess
import sys


def main():
    # Get the project root (assumes this script is in src/scripts)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "../.."))

    # Change to project root
    os.chdir(project_root)

    print("> Running ruff format:")
    format_result = subprocess.run(["ruff", "format", "."], check=False)

    print("\n> Running ruff check with auto-fix:")
    fix_result = subprocess.run(["ruff", "check", "--fix", "."], check=False)

    # Return success only if both commands succeeded
    if format_result.returncode != 0:
        print("❌ ruff format failed")
        return format_result.returncode

    if fix_result.returncode != 0:
        print("❌ ruff check --fix failed")
        return fix_result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
