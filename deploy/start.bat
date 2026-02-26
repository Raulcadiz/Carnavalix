@echo off
title CarnavalPlay Server
color 0A
cls

echo.
echo  =============================================
echo    🎭  CarnavalPlay - Iniciando servidor...
echo  =============================================
echo.

:: Ir a la carpeta raíz del proyecto
cd /d "%~dp0.."

:: Comprobar .env
if not exist ".env" (
    echo  [!] No se encontro el archivo .env
    echo  [!] Copia deploy\.env.example a .env y rellena las API keys.
    echo.
    pause
    exit /b 1
)

:: Activar entorno virtual si existe
if exist "venv\Scripts\activate.bat" (
    echo  [*] Activando entorno virtual...
    call venv\Scripts\activate.bat
) else (
    echo  [!] No se encontro entorno virtual. Usando Python del sistema.
    echo  [!] Recomendado: python -m venv venv ^& pip install -r requirements.txt
)

:: Copiar .env a la raíz si no está
if not exist ".env" (
    copy deploy\.env.example .env
)

:: Arrancar el servidor
echo  [*] Iniciando en http://localhost:5000
echo  [*] Panel admin: http://localhost:5000/admin
echo  [*] Chat 24/7: http://localhost:5000/chat
echo.
echo  Ctrl+C para detener el servidor.
echo.

python -m backend.main

pause
