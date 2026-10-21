# Guía de demostración

Duración sugerida: 12–15 min. Todo corre en tu Mac con datos **ficticios**; nunca toca la base real.

## Antes de empezar (5 min antes)

```sh
./scripts/demo.sh reiniciar      # base de demostración nueva + servidor
```

- Abre `http://localhost:8765/` (pantalla operativa) y, en otra pestaña, `http://localhost:8765/admin.html`.
- Administrador de la demo: **demo** / **demo-tvuaq-26**. Superusuario: **super** / **super-tvuaq-26**.
- La administradora **Ana Sofía** (usuario `coordinacion`) también es operadora: su huella registra su propia asistencia.
- Respaldos: la «USB» de la demo es `/Volumes/TVUAQ-USB/respaldos`. Si no tienes una memoria con ese nombre, verás el aviso de «USB desconectada» (útil para mostrarlo); si quieres mostrarla conectada, renombra una USB a `TVUAQ-USB`.
- Usa **Chrome o Safari** y deja la Mac en hora de México. La demo se probó en Chrome; **prueba Safari antes** si presentarás con él.
- Si algo se atora: `Ctrl+C` y vuelve a correr `./scripts/demo.sh reiniciar`.

## El panel «Modo demostración» (esquina inferior derecha)

Solo existe con el simulador encendido (en la PC real no aparece). Permite:
- **Poner dedo**: simula la huella de alguien (en la PC será el lector real).
- **Hora del sistema**: mueve el reloj para enseñar a tiempo / retardo / falta sin esperar. **Hora real** lo regresa.
- **+31 días** y **Ejecutar borrado de bajas vencidas**: enseña el borrado a los 30 días.
- **Simular que el lector falla**: enseña el aviso en la pantalla operativa cuando el lector no responde.

Turnos de la demo (para elegir a quién usar según el día en que presentes):

| Día | Turnos |
|---|---|
| Lunes | Juan Carlos 07–12 · Luis Eduardo 17–21 |
| Martes | María Fernanda 07–13 · Ana Sofía 13–19 |
| Miércoles | Juan Carlos 15–21 · Luis Eduardo 17–21 |
| Jueves | María Fernanda 07–13 |
| Viernes | Ana Sofía 07–13 · Luis Eduardo 17–21 |

Si presentas en fin de semana, pon la hora en el lunes siguiente.

## Parte 1 · Pantalla operativa (lo que ve el personal)

1. Muestra el reloj y «Coloca tu dedo en el sensor». No hay botones de Entrada/Salida: el sistema decide solo.
2. Pon la hora a **07:03** de un día con turno a las 07:00 → *Poner dedo* → **entrada a tiempo**.
3. Con otra persona, hora **07:07** → **retardo** (5 a 10 min). Con otra, hora **07:12** → **«Se registra falta»** (la entrada sí se registra).
4. Vuelve a poner el mismo dedo enseguida → «Tu registro ya quedó guardado» (antirrebote).
5. Mueve la hora a las 09:00 y pon el dedo del que entró → «Aún no termina tu turno… ¿estás seguro?» → *Registrar salida*.
6. **No reconocida** → mensaje de huella no reconocida.
7. **Registrar incidencia**: abre el formulario, pon el dedo con el formulario vacío (avisa que falta llenarlo y **no** registra entrada), llena los campos (aparece «Listo, coloca tu huella») y pon el dedo → incidencia registrada.

## Parte 2 · Administración (solo administradores)

1. **Seguridad del acceso**: en la pestaña de admin, pon el dedo de un **operador** → no entra. Escribe una contraseña mala → «Usuario o contraseña incorrectos». Entra con demo / demo-tvuaq-26 (o con la huella del administrador).
2. **Operadores**: alta de uno nuevo (nombre en 3 campos, huella, horario). 
3. **Bajas** (lo nuevo): *Dar de baja* → explica el aviso: baja inmediata, 30 días por si fue un error, luego se borra **todo**. Marca «Mostrar operadores dados de baja» → cuenta regresiva. *Reingresar* para mostrar que se revierte.
4. **Borrado a los 30 días**: en el panel, *+31 días* → *Ejecutar borrado de bajas vencidas* → el operador desaparece (en la bitácora solo queda «purga-operador», sin datos personales).
5. **Administradores y superusuario**: alta de otro administrador (prueba una contraseña corta: la rechaza; puedes marcar «también es operador»). Muestra que, con la cuenta `demo`, **no** aparece «Desactivar»; entra con `super` y sí aparece (y nunca sobre sí mismo). Menciona: bloqueo tras 5 intentos, sesión de 30 min, bitácora.
   - Admin que también opera: en la pantalla operativa, con la hora en martes 13:03, pon el dedo de *Ana Sofía (administrador)* → registra su entrada. Luego, con `coordinacion`, intenta justificarse a sí misma: el sistema se lo niega (otro administrador debe hacerlo).
6. **Respaldos**: pestaña *Respaldos* → *Respaldar ahora*: la copia en la PC queda «Verificado» y la USB desconectada se avisa sin romper nada. Con USB conectada, ambos quedan al corriente.
7. **Reportes**: Registro de asistencia (pase de lista del día, lo que acabas de registrar en la Parte 1) → Reporte individual → *Justificar* una falta con motivo → *Editar* un estatus → Incidencias → *Generar PDF*.

## Parte 3 · Qué decir sin que se vea

- **Roles y permisos**: la restricción está en el **servidor**, no solo en la pantalla. Una prueba automática revisa que *toda* ruta administrativa exija sesión de administrador. El operador no tiene forma de modificar nada fuera de entrada, salida e incidencias.
- **Internet / apagones**: nada depende de internet: sin conexión el sistema sigue sirviendo igual. Si se cae el servidor, la pantalla avisa «Sin conexión con el sistema» y **se recupera sola** al volver (se probó con un apagón simulado: los datos quedaron íntegros). Si cambia la hora al resincronizar, queda en bitácora y no rompe los registros.
- **Calidad**: 68 pruebas automáticas, incluida una que verifica que los reportes de la pantalla den exactamente lo mismo que las reglas oficiales del servidor.

## Parte 4 · Lo que todavía NO está (dilo tú antes de que pregunten)

- **Lector de huellas real**: se está probando en la PC del cliente. Hoy la demo usa un simulador.
- **PDF oficial**: sigue la impresión del navegador con membrete provisional; falta el membrete oficial para el PDF definitivo.
- **Instalación en la PC con Windows**, arranque automático y actualización controlada del driver: escritos, sin probar todavía en la PC.
- Cambio visible de la sesión: el formulario de operadores ahora pide nombre y apellidos por separado.

## Al terminar

- *Hora real* en el panel y `Ctrl+C` en la terminal. Nada de la demo toca datos reales.
