@echo off
setlocal
title Open ArchiBook LLM - Menu

:menu
cls
echo ============================================
echo   OPEN ARCHIBOOK LLM - MENU DE OPERACIONES
echo ============================================
echo.
echo   1. Primera instalacion
echo   2. Encender la herramienta
echo   3. Apagar la herramienta
echo   4. Actualizar desde Git y reconstruir
echo   5. Diagnostico
echo   Q. Salir
echo.
choice /c 12345Q /n /m "Seleccione una opcion: "
if errorlevel 6 goto end
if errorlevel 5 call "%~dp006-DIAGNOSTICO.bat" & goto menu
if errorlevel 4 call "%~dp003-ACTUALIZAR.bat" & goto menu
if errorlevel 3 call "%~dp002-APAGAR.bat" & goto menu
if errorlevel 2 call "%~dp001-ENCENDER.bat" & goto menu
if errorlevel 1 call "%~dp000-PRIMERA-INSTALACION.bat" & goto menu

:end
endlocal
