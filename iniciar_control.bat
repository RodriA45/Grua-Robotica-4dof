@echo off
title Panel de Control - Grua Robotica (4 GDL)
color 0B
echo ====================================================================
echo             INICIANDO PANEL DE CONTROL DE LA GRUA ROBOTICA
echo ====================================================================
echo.

REM 1. Si existe el ejecutable portable compilado, ejecutarlo directamente (no requiere Python)
if exist "ControlGrua.exe" (
    echo [OK] Ejecutando version portable independiente (ControlGrua.exe)...
    start "" "ControlGrua.exe"
    exit /b
)

REM 2. Si no esta el ejecutable, intentar con el entorno virtual de Python
if exist ".venv\Scripts\python.exe" (
    echo [OK] Ejecutando mediante entorno virtual Python...
    .venv\Scripts\python.exe control_joystick.py
    goto FIN
)

REM 3. Si no hay entorno virtual, intentar con el Python del sistema
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [INFO] Python detectado en el sistema. Ejecutando script...
    python control_joystick.py
    goto FIN
)

echo.
echo ====================================================================
echo [ERROR] No se pudo iniciar el programa:
echo  1. Asegurate de que 'ControlGrua.exe' este en esta misma carpeta, O
echo  2. Ten instalado Python 3.x con las librerias pygame y pyserial.
echo ====================================================================
echo.
pause

:FIN
if %ERRORLEVEL% neq 0 (
    echo.
    echo Ocurrio un error al ejecutar el programa.
    pause
)
