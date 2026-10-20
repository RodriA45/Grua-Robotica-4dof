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
    echo Abriendo la pagina de GitHub en tu navegador para ver la version actualizada...
    start https://github.com/RodriA45/Grua-Robotica-4dof
    echo.
    pause
    exit /b
)

REM Si la carpeta no tiene .git, conectar automaticamente con el repo
if not exist ".git" (
    echo [INFO] Configurando conexion con GitHub por primera vez...
    git init
    git remote add origin https://github.com/RodriA45/Grua-Robotica-4dof.git
    git fetch origin main
    git reset --hard origin/main
    echo [OK] Sincronizacion inicial completada exitosamente.
    echo.
    goto FIN
)

echo Descargando y aplicando ultimos cambios de GitHub...
echo.
git pull origin main
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

:FIN
echo.
pause
