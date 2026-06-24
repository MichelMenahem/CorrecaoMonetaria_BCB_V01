@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Instalando ambiente virtual
echo ============================================
echo.

python -m venv .venv
if %ERRORLEVEL% NEQ 0 (
    echo ERRO: Python nao encontrado. Instale o Python 3.11+.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
pip install --upgrade pip --quiet
pip install -r requirements.txt

echo.
echo Instalacao concluida. Execute: python main.py
echo.
pause
