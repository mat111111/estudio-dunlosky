@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo  Deteniendo Estudio Dunlosky...
docker compose down
echo  Listo. Tus temas y tu progreso quedan guardados en la carpeta "data".
timeout /t 4 > nul
