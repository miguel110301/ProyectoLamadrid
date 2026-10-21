# Actualización CONTROLADA del driver del lector (Windows 10, PowerShell como administrador). SIN PROBAR: se valida en la PC real.
#
# Idea: el driver se actualiza solo, pero nunca "a ciegas". Cada paso tiene red de seguridad:
#   1) Solo instala el paquete que el equipo dejó aprobado en drivers\lector\nuevo\ (no lo que aparezca en internet).
#   2) Antes: punto de restauración de Windows + respaldo de la base.
#   3) Después: prueba de salud del lector. Si falla, vuelve al driver anterior (drivers\lector\anterior\) y lo deja registrado.
# La tarea programada «TvUAQ-Driver» lo corre cada semana, fuera del horario de operación (ver docs/instalacion-windows.md).
$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
$nuevo = Get-ChildItem (Join-Path $raiz 'drivers\lector\nuevo') -Filter *.msi -ErrorAction SilentlyContinue | Select-Object -First 1
$anterior = Get-ChildItem (Join-Path $raiz 'drivers\lector\anterior') -Filter *.msi -ErrorAction SilentlyContinue | Select-Object -First 1
$bitacora = Join-Path $raiz 'data\actualizacion-driver.log'
function Registrar($t) { "$(Get-Date -Format s)  $t" | Add-Content $bitacora; Write-Host $t }

function Lector-Sano {
    # El lector USB (identificador del fabricante 05BA) debe aparecer en estado OK y el servidor debe verlo funcionando
    $dev = Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\VID_05BA*' }
    if (-not $dev -or ($dev | Where-Object Status -ne 'OK')) { return $false }
    try { return (Invoke-RestMethod http://127.0.0.1:8765/api/kiosko/estado-lector -TimeoutSec 10).ok } catch { return $false }
}

if (-not $nuevo) { Registrar 'Sin paquete nuevo aprobado: no se toca nada.'; if (-not (Lector-Sano)) { Registrar 'ALERTA: el lector no responde.' }; exit 0 }

Registrar "Actualizando driver con $($nuevo.Name)"
Checkpoint-Computer -Description 'Antes de actualizar driver del lector TvUAQ' -RestorePointType MODIFY_SETTINGS
& (Join-Path $raiz 'backend\.venv\Scripts\python.exe') -m app.respaldar
Start-Process msiexec.exe -ArgumentList "/i `"$($nuevo.FullName)`" /qn /norestart" -Wait
Start-Sleep -Seconds 20

if (Lector-Sano) {
    Registrar 'Driver nuevo OK. Se conserva el anterior como respaldo.'
    # El que estaba instalado pasa a ser «anterior»; el aprobado pasa a ser el vigente
    Remove-Item (Join-Path $raiz 'drivers\lector\anterior\*') -Force -ErrorAction SilentlyContinue
    Move-Item $nuevo.FullName (Join-Path $raiz 'drivers\lector\anterior\')
} elseif ($anterior) {
    Registrar 'ALERTA: el lector falló con el driver nuevo. Volviendo al anterior.'
    Start-Process msiexec.exe -ArgumentList "/x `"$($nuevo.FullName)`" /qn /norestart" -Wait
    Start-Process msiexec.exe -ArgumentList "/i `"$($anterior.FullName)`" /qn /norestart" -Wait
    Start-Sleep -Seconds 20
    Registrar ("Resultado tras revertir: " + $(if (Lector-Sano) { 'lector OK' } else { 'el lector sigue sin responder; revisar a mano' }))
} else {
    Registrar 'ALERTA: el lector falló y no hay driver anterior guardado. Revisar a mano.'
}
