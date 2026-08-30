#!/usr/bin/env bash

set -u
set -o pipefail

run_check() {
    local name="$1"
    shift

    echo
    echo "==> ${name}"

    "$@"
    local exit_code=$?

    if [ "$exit_code" -ne 0 ]; then
        echo
        echo "ERROR: ${name} failed with exit code ${exit_code}."
        exit "$exit_code"
    fi

    echo "OK: ${name}"
}

run_check "pytest" uv run pytest
run_check "ruff check" uv run ruff check .
run_check "mypy" uv run mypy
run_check "pylint" uv run pylint --fail-under=9.0 src tests
run_check "ruff format" uv run ruff format --check .

echo
echo "All checks passed successfully."
