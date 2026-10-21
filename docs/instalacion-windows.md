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
| Windows | Sin actualización automática de drivers (ver abajo). |
| Cambios de código | Solo tú, desde GitHub: en la PC se corre `scripts/actualizar.ps1` (pendiente) a mano. No hay despliegue automático. |

## Windows Update y drivers

- Directiva para que Windows no reemplace drivers por su cuenta: *Editor de directivas de grupo → Configuración del equipo → Plantillas administrativas → Componentes de Windows → Windows Update → «No incluir controladores con las actualizaciones de Windows» = Habilitada*. (Windows 10 Pro; en Home se hace por registro.)
- Horas activas amplias y reinicios fuera de horario de operación.
- Windows 10 terminó su soporte en octubre de 2025: sin actualizaciones de seguridad gratuitas. Con internet siempre conectado, el servidor solo escucha en `127.0.0.1` y el firewall debe bloquear todo lo entrante; no habilitar Escritorio Remoto ni carpetas compartidas.

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
