// Calcula con el core.js del frontend los resúmenes de un snapshot (JSON por stdin) y los imprime como JSON.
const fs = require('fs');
const vm = require('vm');
const entrada = JSON.parse(fs.readFileSync(0, 'utf8'));
const ventana = { TV: {} };
vm.runInNewContext(fs.readFileSync(entrada.core, 'utf8'), { window: ventana, Date, Math, JSON, String, Number, Object, Array });
const TV = ventana.TV;
TV.db.cargar(entrada.datos);
const salida = {};
for (const op of TV.db.get().operadores) {
  const r = TV.calc.resumen(op, entrada.desde, entrada.hasta, entrada.ahora);
  salida[op.id] = {
    asistencias: r.asistencias, faltas: r.faltas, retardos: r.retardos, incompletos: r.incompletos,
    justificadas: r.justificadas, sin_salida: r.sinSalida, faltante_min: r.faltanteMin,
    estados: r.filas.map((f) => `${f.fecha} ${f.turno.inicio} ${f.estado}`),
  };
}
process.stdout.write(JSON.stringify(salida));
