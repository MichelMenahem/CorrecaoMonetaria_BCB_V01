@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  Gerando executavel com PyInstaller
echo ============================================
echo.

call .venv\Scripts\activate.bat

pip install pyinstaller --quiet

echo Limpando builds anteriores...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo.
echo Executando PyInstaller...
echo.

pyinstaller ^
    --onefile ^
    --console ^
    --name=CorrecaoMonetaria_BCB ^
    --hidden-import requests ^
    main.py

echo.
if %ERRORLEVEL% == 0 (
    echo Executavel gerado com sucesso:
    echo   dist\CorrecaoMonetaria_BCB.exe
    echo.
    echo ATENCAO: necessita conexao com a internet para acessar o BCB.
) else (
    echo ERRO ao gerar o executavel. Verifique as mensagens acima.
)

pause
