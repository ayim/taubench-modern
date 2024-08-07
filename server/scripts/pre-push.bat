@echo off
echo Running pre-push checks...
make test
if %errorlevel% neq 0 exit /b %errorlevel%
echo Pre-push checks passed!
