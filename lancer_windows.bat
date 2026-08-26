@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creation de l'environnement Python...
    py -3.11 -m venv .venv
    if errorlevel 1 (
        echo Python 3.11 introuvable. Tentative avec la version Python disponible...
        py -m venv .venv
    )
    if errorlevel 1 goto :failure
)

if not exist ".venv\openmill-installed.flag" (
    echo Installation de l'interface graphique et de VTK...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    if errorlevel 1 goto :failure
    ".venv\Scripts\python.exe" -m pip install -e ".[gui]"
    if errorlevel 1 goto :failure
    type nul > ".venv\openmill-installed.flag"
)

".venv\Scripts\python.exe" -m openmill
if errorlevel 1 goto :failure
exit /b 0

:failure
echo.
echo Le lancement a echoue. Verifie que Python 3.11 ou plus recent est installe.
pause
exit /b 1

