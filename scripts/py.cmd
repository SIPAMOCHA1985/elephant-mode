@echo off
rem Windows twin of scripts/py, for Codex (it runs hooks through cmd.exe): the first working Python 3.9+.
rem `python3` is often the Microsoft Store stub on Windows, so each name is tried until one really runs.
for %%P in ("py -3" python python3) do (
  %%~P -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>&1 && (set "EM_PY=%%~P" & goto run)
)
echo elephant-mode: Python 3.9+ not found. Install it from python.org and restart Codex. 1>&2
exit /b 1
:run
%EM_PY% %*
