# Instalación en la PC (Windows 10, PowerShell). SIN PROBAR: se valida en la PC real.
# Uso (PowerShell como administrador, desde la carpeta del proyecto):  .\scripts\instalar.ps1
# Requisitos previos: Python 3.14 (64 bits) instalado "para todos los usuarios" y el driver del lector (ver docs/instalacion-windows.md).
$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

# 1) Entorno de Python aislado, con los paquetes de vendor\wheels: no usa internet
python -m venv backend\.venv
& backend\.venv\Scripts\python.exe -m pip install --no-index --find-links backend\vendor\wheels -r backend\requirements.txt

# 2) Carpetas de datos (fuera del código; el repositorio las ignora)
New-Item -ItemType Directory -Force -Path data, backups | Out-Null

# 3) Primer administrador (no existe usuario por defecto)
Push-Location backend
$env:TVUAQ_DB = Join-Path $raiz 'data\tvuaq.db'
& .venv\Scripts\python.exe -m app.crear_admin
Pop-Location
