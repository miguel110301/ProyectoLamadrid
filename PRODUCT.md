# Product

## Register

product

## Users

Dos públicos en una sola PC de escritorio (Windows 10, monitor Dell) del Control Maestro de TvUAQ, en la Universidad Autónoma de Querétaro:

- **Personal operador** (estudiantes que cubren turnos del Control Maestro). Llegan, colocan el dedo en el sensor y se van a operar. No son técnicos, no quieren aprender nada, y están en medio de una tarea de transmisión en vivo. Lo que más usan es la pantalla operativa; además registran incidencias durante el turno.
- **Administrador** (responsable del Control Maestro). Entra de vez en cuando para dar de alta personal, ajustar horarios y sacar reportes (asistencia e incidencias, por periodo) que se exportan a PDF sobre hoja membretada y se archivan.

La pantalla operativa queda abierta de fondo siempre que la computadora esté encendida, arranca sola con Windows y se lee de un vistazo. Si hay un apagón, el sistema debe volver solo.

## Product Purpose

Llevar el registro de entrada y salida del personal operador del Control Maestro por huella biométrica, calcular automáticamente asistencias, faltas, retardos (más de 15 min), turnos incompletos y tiempo por cumplir, y registrar las incidencias de cada turno (cortes de CFE, fallas de equipo, sustitución de pautas, etc.). Éxito: nadie dice "estaba cerrado el programa", ningún registro se pierde, y el administrador saca un reporte formal en un minuto.

## Brand Personality

Televisiva, con energía, institucional. Hereda la identidad de tv.uaq.mx: fondo blanco, degradado violeta-azul en la barra superior, acento morado #520099, Raleway/Roboto/Poppins, pie negro. Más presencia de marca y color que un sistema interno gris, sin dejar de ser claro y confiable. Voz: directa, en español neutro, frases cortas, sin tecnicismos ni exclamaciones.

## Anti-references

- Que parezca hecho con IA o con una plantilla genérica: tarjetas idénticas con icono en círculo, sombras suaves en todo, degradados decorativos en superficies, bordes de color a un lado como adorno, métricas gigantes tipo SaaS.
- Tema oscuro tipo "panel de control" (ya se descartó: el sitio de la marca es blanco).
- Apps administrativas grises y anónimas sin relación con TvUAQ.
- Efectos decorativos, animación de entrada, modales innecesarios.

## Design Principles

1. **Se lee de un vistazo, a distancia.** El estado del sensor y el resultado de cada registro se entienden en un segundo, con tipografía grande y color semántico, sin depender solo del color.
2. **Siempre listo.** La pantalla operativa nunca pide un clic antes de aceptar una huella; los botones son opcionales. Un error no deja la pantalla en un estado que alguien tenga que "arreglar".
3. **La marca es TvUAQ, no una plantilla.** Colores, tipografías y la forma de la barra salen del sitio de la universidad; el color de marca se usa con intención, con más presencia en lo operativo que en lo administrativo.
4. **Familiar para quien administra.** Tablas, filtros y formularios convencionales y consistentes; la creatividad se reserva para la pantalla operativa y los reportes.
5. **El papel también es interfaz.** Los PDF son el producto final que se firma y archiva: deben verse institucionales y completos sin ajustes.

## Accessibility & Inclusion

WCAG 2.1 AA: contraste mínimo 4.5:1 en texto, foco visible, el estado nunca se comunica solo con color (siempre hay texto o icono), objetivos de al menos 44 px en la pantalla operativa, respetar `prefers-reduced-motion`. Idioma español (lang="es").
