# Manuales · Control Maestro TvUAQ

Manuales de entrega (contrato, Anexo 5) con el estilo FRACTAL, listos para imprimir en tamaño carta.

| Archivo | Contenido |
|---|---|
| `Manual de usuario - Control Maestro TvUAQ.pdf` | Personal operador y administradores: registro con huella, incidencias, administración, reportes, PDF, justificaciones, administradores, respaldos, reglas de asistencia y preguntas frecuentes (22 páginas). |
| `Manual técnico - Control Maestro TvUAQ.pdf` | Arquitectura, requisitos, kit, instalación paso a paso, prueba final, operación, respaldos y restauración, actualización, solución de problemas, configuración, seguridad y construcción del kit (17 páginas). |
| `manual-de-usuario.html`, `manual-tecnico.html`, `manual.css` | Fuente de los PDF. |
| `img/` | Capturas del sistema en modo demostración (datos ficticios) y logotipo de FRACTAL. |
| `generar_pdf.mjs` | Vuelve a generar los dos PDF a partir de los HTML. |

## Qué versión describen

El **sistema final entregado** (proyecto integrado `control_maestro`, commit `818a06d` del 31-oct-2026), **no** el código
de este repositorio: botones Entrada | Salida | Registrar incidencia, tolerancia de retardo de 15 minutos (configurable),
PDF con ReportLab, lector con driver WBF y kit de instalación con `.bat` numerados. La parte técnica sale de su
`docs/instalacion.md` y del código; cada mensaje de pantalla se copió del código de la interfaz.

## Regenerar los PDF

1. Editar los `.html` (abrirlos en Chrome para ver el resultado; en pantalla se ven como hojas).
2. En una carpeta de trabajo con `npm i puppeteer-core@23` y Google Chrome instalado:
   `node /ruta/a/docs/manuales/generar_pdf.mjs`
3. Revisar que ninguna página quede casi vacía (una figura o una nota sola); se corrige con las clases `chica` / `mini`
   de las figuras o envolviendo el bloque en `<div style="break-inside: avoid">`.

Si cambia la interfaz del sistema, hay que volver a tomar las capturas de `img/`.

## Pendiente de actualizar cuando llegue

- Membrete oficial y logotipo (hoy los PDF del sistema usan uno provisional).
- Texto oficial del aviso de privacidad (el del sistema es provisional).
- Tolerancia de retardo confirmada por escrito con el cliente (hoy 15 min).
