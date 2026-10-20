@echo off
title Actualizar Proyecto desde GitHub
color 0A
echo ====================================================================
echo             ACTUALIZAR PROYECTO DESDE REPOSITORIO GITHUB
echo ====================================================================
echo.

REM Comprobar si Git esta instalado en el sistema
where git >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [AVISO] Git no esta instalado en este equipo.
    echo Para actualizar sin Git, descarga el archivo ZIP desde GitHub.
    echo.
    pause
    exit /b
)

REM Comprobar si esta carpeta es un repositorio Git (.git)
if not exist ".git" (
    echo [INFO] Esta carpeta aun no esta inicializada con Git.
    echo.
    echo Para conectar esta carpeta a tu GitHub por primera vez:
    echo   1. Abre una terminal aqui.
    echo   2. Ejecuta: git init
    echo   3. Ejecuta: git remote add origin https://github.com/RodriA45/Grua-Robotica-4dof.git
    echo   4. Ejecuta: git pull origin main
    echo.
    pause
    exit /b
)

echo Descargando y combinando ultimos cambios de GitHub...
echo.
git pull
if %ERRORLEVEL% equ 0 (
    echo.
    echo ====================================================================
    echo [EXITO] Proyecto actualizado correctamente con los ultimos cambios.
    echo ====================================================================
) else (
    echo.
    echo [AVISO] No se pudo completar la actualizacion automatica.
    echo Revisa tu conexion a internet o si hay archivos modificados localmente.
)

echo.
pause
