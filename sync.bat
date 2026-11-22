@echo off
rem Copy the built kit (export\*.glb, *.json) into a game project:
rem   sync.bat "C:\path\to\Project\Assets\Castle\Kit"
rem or put that folder in sync_target.txt beside this file (git-ignored) and run sync.bat alone.
setlocal
set "TARGET=%~1"
if "%TARGET%"=="" if exist "%~dp0sync_target.txt" set /p TARGET=<"%~dp0sync_target.txt"
if "%TARGET%"=="" (
  echo usage: sync.bat "path\to\Assets\Castle\Kit"   or put the folder in sync_target.txt
  exit /b 1
)
robocopy "%~dp0export" "%TARGET%" *.glb *.json /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 exit /b 1
exit /b 0
