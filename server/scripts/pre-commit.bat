@echo off
echo Running pre-commit checks...
make format
if %errorlevel% neq 0 exit /b %errorlevel%
make lint
if %errorlevel% neq 0 exit /b %errorlevel%
echo Pre-commit checks passed!
