@echo off
setlocal

echo.
echo ========================================
echo Running pytest
echo ========================================
uv run pytest
if errorlevel 1 goto pytest_failed
echo OK: pytest passed.

echo.
echo ========================================
echo Running Ruff
echo ========================================
uv run ruff check .
if errorlevel 1 goto ruff_failed
echo OK: Ruff passed.

echo.
echo ========================================
echo Running mypy
echo ========================================
uv run mypy
if errorlevel 1 goto mypy_failed
echo OK: mypy passed.

echo.
echo ========================================
echo Running pylint
echo ========================================
uv run pylint --fail-under=9.0 src tests
if errorlevel 1 goto pylint_failed
echo OK: pylint passed.

echo.
echo ========================================
echo Running Ruff format check
echo ========================================
uv run ruff format --check .
if errorlevel 1 goto format_failed
echo OK: Ruff format check passed.

echo.
echo ========================================
echo ALL CHECKS PASSED
echo ========================================
exit /b 0


:pytest_failed
echo.
echo ERROR: pytest failed.
exit /b 1

:ruff_failed
echo.
echo ERROR: Ruff check failed.
exit /b 1

:mypy_failed
echo.
echo ERROR: mypy failed.
exit /b 1

:pylint_failed
echo.
echo ERROR: pylint failed.
exit /b 1

:format_failed
echo.
echo ERROR: Ruff format check failed.
exit /b 1
