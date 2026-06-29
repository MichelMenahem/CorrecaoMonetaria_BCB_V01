@echo off
REM ============================================================
REM  agendar_sync.bat
REM  Cria/recria o agendamento do sync de indices BCB.
REM  Execute como Administrador.
REM ============================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0agendar_sync.ps1"
pause
