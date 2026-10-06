@echo off
cd /d "%~dp0"
py -3 app.py
if errorlevel 1 (
  echo.
  echo No abrio. Hace falta Python 3 de python.org, con tkinter.
  echo No hay que instalar librerias.
  pause
)
