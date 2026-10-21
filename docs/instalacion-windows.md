# Instalación y mantenimiento en la PC (Windows 10)

Plan para que el sistema funcione años sin tocarse. Estado: **escrito en Mac, sin probar en Windows**; se valida en la PC real junto con el lector.

## Principio: congelar, no actualizar

Un sistema que debe "funcionar casi para siempre" se mantiene **fijo**; las actualizaciones automáticas son lo que lo rompe. Por eso:

| Pieza | Cómo queda fija |
|---|---|
| Paquetes de Python | `backend/requirements.txt` con versiones exactas + los `.whl` en `backend/vendor/wheels/` (instalación sin internet). |
| Python | Una versión fija (3.14, 64 bits), instalada una vez. Misma versión que usan las pruebas. |
| Driver del lector (U.are.U 4500) | Instalador **Non-WBF 4.1.1.221** guardado en la USB de respaldo. NO instalar el driver WBF/Windows Hello: son incompatibles. |
| SDK del lector | Pendiente: aún no hay SDK ni licencia. Se agrega a `backend/app/lector_digitalpersona.py` con la misma interfaz que el simulador. |
| Windows | Sin reemplazo automático del driver del lector; se actualiza solo por el camino controlado (ver abajo). |
| Cambios de código | Solo tú, desde GitHub: en la PC se corre `scripts/actualizar.ps1` (pendiente) a mano. No hay despliegue automático. |

## Drivers: actualización automática y controlada

Un driver que se actualiza solo y sin freno es justo lo que puede dejar de funcionar el lector de un día para otro. Por eso se actualiza
**automáticamente, pero con red de seguridad**:

1. **Qué se instala lo decide el equipo, no internet**: solo el paquete que se deja aprobado en `drivers\lector\nuevo\` (por ejemplo, una versión nueva de HID). Los cambios llegan por GitHub, como el resto del sistema.
2. **Antes de instalar**: punto de restauración de Windows y respaldo de la base (`python -m app.respaldar`).
3. **Después de instalar**: prueba de salud (el lector aparece en estado OK y el servidor lo ve funcionando). Si falla, vuelve solo al driver anterior guardado en `drivers\lector\anterior\` y lo deja en `data\actualizacion-driver.log`.
4. **Vigilancia continua**: el servidor consulta el estado del lector; si deja de responder (por una actualización de Windows, un cable, etc.) la pantalla operativa lo avisa en vez de quedarse esperando en silencio.
5. **Windows Update** no reemplaza el driver del lector por su cuenta (directiva «No incluir controladores con las actualizaciones de Windows»): así solo cambia por el camino controlado de arriba.

La tarea programada «TvUAQ-Driver» corre `scripts/actualizar-driver.ps1` cada semana, fuera del horario de operación:

```powershell
$a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-ExecutionPolicy Bypass -File "C:\TvUAQ\scripts\actualizar-driver.ps1"'
$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3am
Register-ScheduledTask -TaskName 'TvUAQ-Driver' -Action $a -Trigger $t -RunLevel Highest
```

> Estado: la vigilancia del lector en pantalla **está construida y probada**; el script `actualizar-driver.ps1` está escrito pero **sin probar** (necesita Windows y el lector).
> Para el driver Non-WBF no encontré un canal oficial de actualización automática del fabricante: por eso el paquete nuevo lo aprueba el equipo.

## Respaldos

- **Qué**: copia de la base con la API de respaldo de SQLite, verificada (`integrity_check`) y con huella SHA-256. Cada copia aparece con su nombre final solo cuando ya está completa.
- **Dónde**: carpeta en la PC (`TVUAQ_RESPALDO_LOCAL`, por defecto `backups\`) y memoria USB (`TVUAQ_RESPALDO_USB`, por ejemplo `E:\TvUAQ`). Si la USB no está conectada no pasa nada: se avisa en la pantalla de administración («Respaldos»).
- **Cuándo**: cada madrugada, y al encender la PC si se pasó más de un día. También con el botón «Respaldar ahora» o `python -m app.respaldar`.
- **Cuánto se guarda**: 7 diarios + 4 semanales (~4 semanas). Es corto a propósito: el sistema borra todo de un operador a los 30 días de su baja y los respaldos no deben guardar esos datos por meses.
- **Restaurar**: `python -m app.restaurar --lista` y `python -m app.restaurar <archivo>` con el servidor apagado. Verifica el respaldo antes y conserva la base anterior aparte.
- **La USB contiene datos personales**: protegerla con BitLocker To Go (o equivalente) y guardarla en un lugar seguro.

## Si se va el internet o la luz

- Nada del sistema depende de internet.
- Si cambia la hora al resincronizar, el sistema lo detecta y lo deja en la bitácora (`salto-reloj`); el antirrebote usa reloj monotónico y una salida nunca queda antes de su entrada.
- Tras un apagón la base no se corrompe (WAL + `synchronous=FULL`); la tarea programada vuelve a levantar todo al iniciar sesión.
- En la BIOS: «Restore on AC Power Loss = Power On» para que la PC encienda sola cuando vuelva la luz. Y configurar inicio de sesión automático.

## Arranque automático

Tarea programada «TvUAQ» al iniciar sesión, que ejecuta `scripts/iniciar.ps1` y se reinicia sola si falla:

```powershell
$a = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-ExecutionPolicy Bypass -File "C:\TvUAQ\scripts\iniciar.ps1"'
$t = New-ScheduledTaskTrigger -AtLogOn
$s = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'TvUAQ' -Action $a -Trigger $t -Settings $s
```

## Pendiente de probar en la PC

1. Instalar el driver Non-WBF y ver el lector en el Administrador de dispositivos.
2. `scripts/instalar.ps1` completo, sin internet.
3. Que `scripts/iniciar.ps1` abra el navegador en pantalla completa.
4. SDK del lector: captura, identificación y comparación contra la base.
5. Cortar la luz en medio de un registro y verificar `PRAGMA integrity_check`.
