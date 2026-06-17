@echo off
title BOT Dashboard - Inicio Automatico
color 0A
cls

echo.
echo  =====================================================
echo   BOT DASHBOARD - Iniciando todos los servicios...
echo  =====================================================
echo.

:: ─── Configuracion de rutas ───────────────────────────────────────
set "BASE=C:\Users\Usuario\Desktop\Programacion"
set "DASHBOARD_DIR=%BASE%\Dashboard-BOTS"
set "LINKEDIN_DIR=%BASE%\Linkedin-AG"
set "MERCADO_DIR=%BASE%\MercadoPublico-AG (API)"

:: Esperar 10 segundos al inicio para que Windows termine de cargar
echo [1/5] Esperando que el sistema termine de cargar...
timeout /t 10 /nobreak >nul

:: ─── 1. Abrir el Dashboard en el navegador ────────────────────────
echo [2/5] Abriendo Dashboard de monitoreo...
start "" "http://localhost:9191"

:: ─── 2. Iniciar servidor HTTP para el dashboard ───────────────────
echo [3/5] Iniciando servidor del Dashboard (puerto 9191)...
start "Dashboard Server" /min cmd /c "set PYTHONUTF8=1 && python \"%DASHBOARD_DIR%\server.py\""
timeout /t 3 /nobreak >nul

:: ─── 3. MercadoPublico: primer snapshot al arrancar ───────────────
echo [4/5] Ejecutando snapshot de MercadoPublico-AG...
cd /d "%MERCADO_DIR%"
start "MercadoPublico Snapshot" /min cmd /c "npm run snapshot:compra-agil >> scripts\update-compra-agil.log 2>&1 && echo [AUTO-INICIO] Snapshot OK >> scripts\update-compra-agil.log"

:: ─── 4. LinkedIn dashboard_app (lanzar automáticamente) ───────────────────────
echo [5/5] Iniciando LinkedIn-AG Dashboard...
if exist "%LINKEDIN_DIR%\linkedin_state.json" (
    start "" /D "%LINKEDIN_DIR%" python dashboard_app.py --autostart
    echo      Dashboard de LinkedIn lanzado con auto-inicio
) else (
    echo      ADVERTENCIA: No hay sesion de LinkedIn guardada
    echo      Inicia dashboard_app.py manualmente para hacer login
)

:: ─── 5. Abrir el navegador con el dashboard ───────────────────────
timeout /t 3 /nobreak >nul
start "" "http://localhost:9191"

echo.
echo  =====================================================
echo   Todos los servicios iniciados correctamente!
echo  ─────────────────────────────────────────────────
echo   Dashboard: http://localhost:9191
echo   LinkedIn-AG: %LINKEDIN_DIR%
echo   MercadoPublico-AG: %MERCADO_DIR%
echo  =====================================================
echo.

exit
