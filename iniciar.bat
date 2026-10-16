@echo off
chcp 65001 > nul
title Estudio Dunlosky
cd /d "%~dp0"

echo.
echo  Estudio Dunlosky
echo  ----------------
echo.

docker info > nul 2>&1
if errorlevel 1 (
  echo  Docker Desktop no esta abierto.
  echo  Abrilo desde el menu Inicio, espera a que diga "Engine running" y volve a ejecutar este archivo.
  echo.
  pause
  exit /b 1
)

echo  Preparando la aplicacion. La primera vez tarda unos minutos...
docker compose up -d --build
if errorlevel 1 (
  echo.
  echo  No se pudo iniciar. Revisa el mensaje de arriba.
  pause
  exit /b 1
)

set /a intentos=0
:esperar
curl -s -o nul http://localhost:8000/api/health && goto listo
set /a intentos+=1
if %intentos% geq 40 goto listo
timeout /t 2 /nobreak > nul
goto esperar

:listo
echo.
echo  Listo. Abriendo http://localhost:8000
start "" http://localhost:8000
echo.
echo  La app sigue funcionando en segundo plano. Para apagarla, ejecuta detener.bat
timeout /t 6 > nul
