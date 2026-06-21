@echo off
REM =====================================================================
REM           DELL DRAKE INFRASTRUCTURE COMMAND CENTER - LAUNCHER
REM =====================================================================
REM Windows Batch script wrapper to execute the PowerShell startup script.
REM =====================================================================

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
