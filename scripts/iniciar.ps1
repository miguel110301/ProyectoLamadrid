# Arranque: servidor local + navegador en pantalla completa. SIN PROBAR: se valida en la PC real.
# Lo lanza la tarea programada "TvUAQ" al iniciar sesión (ver docs/instalacion-windows.md).
$raiz = Split-Path -Parent $PSScriptRoot
$py = Join-Path $raiz 'backend\.venv\Scripts\python.exe'
$env:TVUAQ_DB = Join-Path $raiz 'data\tvuaq.db'
$env:TVUAQ_SIMULADOR = '0'   # producción: sin lector simulado

# El servidor se relanza solo si se cae; el apagón se resuelve porque la base usa WAL + sincronización completa
$servidor = Start-Process -FilePath $py -WorkingDirectory (Join-Path $raiz 'backend') -WindowStyle Hidden -PassThru `
    -ArgumentList '-m', 'uvicorn', 'app.main:app_produccion', '--factory', '--host', '127.0.0.1', '--port', '8765'

# Espera a que responda antes de abrir el navegador
for ($i = 0; $i -lt 60; $i++) {
    try { Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/api/kiosko/tipos-incidencia | Out-Null; break } catch { Start-Sleep -Seconds 1 }
}
Start-Process msedge -ArgumentList '--kiosk', 'http://127.0.0.1:8765/', '--edge-kiosk-type=fullscreen', '--no-first-run'

# Si el servidor termina, este script termina con error y la tarea programada lo reinicia
$servidor.WaitForExit()
exit 1
