-- Control Maestro TvUAQ · esquema SQLite
-- Convenciones:
--   * Marcas de tiempo (_ts): milisegundos desde 1970 en UTC (INTEGER). No dependen del reloj local ni de horario de verano.
--   * Fechas (fecha, vigente_*): 'YYYY-MM-DD' en la zona horaria configurada. Horas de turno: 'HH:MM'.
--   * dia_semana: 0 = domingo ... 6 = sábado (igual que el prototipo).
--   * Faltas y pendientes NO se guardan: se calculan al vuelo desde `horario` (ver app/reglas.py).
--   * Nada con historial se borra en cascada (ON DELETE RESTRICT). El único borrado es la purga a los 30 días de la baja.

CREATE TABLE IF NOT EXISTS administrador (
    id            INTEGER PRIMARY KEY,
    usuario       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    nombre        TEXT    NOT NULL,
    clave_hash    TEXT    NOT NULL,                       -- scrypt, nunca la clave
    activo        INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_ts     INTEGER NOT NULL,
    creado_por    INTEGER REFERENCES administrador (id) ON DELETE RESTRICT,
    intentos_fallidos INTEGER NOT NULL DEFAULT 0,
    bloqueado_hasta_ts INTEGER
);

CREATE TABLE IF NOT EXISTS operador (
    id            INTEGER PRIMARY KEY,
    nombres       TEXT    NOT NULL,
    ap_paterno    TEXT    NOT NULL,
    ap_materno    TEXT    NOT NULL DEFAULT '',
    nacimiento    TEXT    NOT NULL,
    expediente    TEXT    NOT NULL UNIQUE,
    carrera       TEXT    NOT NULL DEFAULT '',
    alta_fecha    TEXT    NOT NULL,
    activo        INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

-- Cada baja es un periodo. Mientras haya uno abierto (hasta_ts NULL) el operador está inactivo:
-- no se identifica con la huella, no genera turnos ni faltas. Un reingreso cierra el periodo.
-- 30 días después de abrirse la baja, la purga borra todo lo del operador.
CREATE TABLE IF NOT EXISTS periodo_baja (
    id            INTEGER PRIMARY KEY,
    id_operador   INTEGER NOT NULL REFERENCES operador (id) ON DELETE RESTRICT,
    desde_ts      INTEGER NOT NULL,
    hasta_ts      INTEGER,
    motivo        TEXT    NOT NULL CHECK (motivo IN ('renuncia', 'despido', 'fin-de-contrato', 'otro')),
    baja_por      INTEGER NOT NULL REFERENCES administrador (id) ON DELETE RESTRICT,
    CHECK (hasta_ts IS NULL OR hasta_ts >= desde_ts)
);
-- A lo más una baja abierta por operador
CREATE UNIQUE INDEX IF NOT EXISTS ux_baja_abierta ON periodo_baja (id_operador) WHERE hasta_ts IS NULL;

CREATE TABLE IF NOT EXISTS horario (
    id             INTEGER PRIMARY KEY,
    id_operador    INTEGER NOT NULL REFERENCES operador (id) ON DELETE RESTRICT,
    dia_semana     INTEGER NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),
    hora_inicio    TEXT    NOT NULL,
    hora_fin       TEXT    NOT NULL,
    vigente_desde  TEXT    NOT NULL,
    vigente_hasta  TEXT,                                  -- NULL = sigue vigente
    CHECK (hora_fin > hora_inicio),
    CHECK (vigente_hasta IS NULL OR vigente_hasta >= vigente_desde)
);
CREATE INDEX IF NOT EXISTS ix_horario_operador ON horario (id_operador, vigente_desde);

-- Huella: exactamente un dueño (operador o administrador). La plantilla se borra con la purga.
CREATE TABLE IF NOT EXISTS huella (
    id               INTEGER PRIMARY KEY,
    id_operador      INTEGER REFERENCES operador (id) ON DELETE RESTRICT,
    id_administrador INTEGER REFERENCES administrador (id) ON DELETE RESTRICT,
    plantilla        BLOB    NOT NULL,
    creado_ts        INTEGER NOT NULL,
    CHECK ((id_operador IS NULL) <> (id_administrador IS NULL))
);

CREATE TABLE IF NOT EXISTS registro_asistencia (
    id            INTEGER PRIMARY KEY,
    id_operador   INTEGER NOT NULL REFERENCES operador (id) ON DELETE RESTRICT,
    id_horario    INTEGER NOT NULL REFERENCES horario (id) ON DELETE RESTRICT,
    fecha         TEXT    NOT NULL,
    entrada_ts    INTEGER NOT NULL,
    salida_ts     INTEGER,
    salida_anticipada INTEGER NOT NULL DEFAULT 0 CHECK (salida_anticipada IN (0, 1)),
    CHECK (salida_ts IS NULL OR salida_ts >= entrada_ts)
);
-- Un apagón puede duplicar una lectura: la base misma impide dos registros del mismo turno
CREATE UNIQUE INDEX IF NOT EXISTS ux_registro_turno ON registro_asistencia (id_operador, id_horario, fecha);
CREATE INDEX IF NOT EXISTS ix_registro_fecha ON registro_asistencia (fecha);

-- Justificar y Editar usan la clave (operador, horario, fecha) y no id_registro: una falta no tiene fila de registro.
CREATE TABLE IF NOT EXISTS justificacion (
    id            INTEGER PRIMARY KEY,
    id_operador   INTEGER NOT NULL REFERENCES operador (id) ON DELETE RESTRICT,
    id_horario    INTEGER NOT NULL REFERENCES horario (id) ON DELETE RESTRICT,
    fecha         TEXT    NOT NULL,
    motivo        TEXT    NOT NULL CHECK (length(trim(motivo)) > 0),
    creado_ts     INTEGER NOT NULL,
    creado_por    INTEGER NOT NULL REFERENCES administrador (id) ON DELETE RESTRICT,
    UNIQUE (id_operador, id_horario, fecha)
);

CREATE TABLE IF NOT EXISTS ajuste_estatus (
    id            INTEGER PRIMARY KEY,
    id_operador   INTEGER NOT NULL REFERENCES operador (id) ON DELETE RESTRICT,
    id_horario    INTEGER NOT NULL REFERENCES horario (id) ON DELETE RESTRICT,
    fecha         TEXT    NOT NULL,
    estado        TEXT    NOT NULL CHECK (estado IN ('asistencia', 'retardo', 'falta')),
    motivo        TEXT    NOT NULL DEFAULT '',
    creado_ts     INTEGER NOT NULL,
    creado_por    INTEGER NOT NULL REFERENCES administrador (id) ON DELETE RESTRICT,
    UNIQUE (id_operador, id_horario, fecha)
);

CREATE TABLE IF NOT EXISTS tipo_incidencia (
    id                 TEXT PRIMARY KEY,
    nombre             TEXT    NOT NULL,
    requiere_duracion  INTEGER NOT NULL CHECK (requiere_duracion IN (0, 1))
);

CREATE TABLE IF NOT EXISTS incidencia (
    id             INTEGER PRIMARY KEY,
    id_operador    INTEGER NOT NULL REFERENCES operador (id) ON DELETE RESTRICT,
    id_tipo        TEXT    NOT NULL REFERENCES tipo_incidencia (id) ON DELETE RESTRICT,
    fecha          TEXT    NOT NULL,
    hora           TEXT    NOT NULL,
    registrado_ts  INTEGER NOT NULL,
    programa       TEXT    NOT NULL DEFAULT '',
    duracion_min   INTEGER CHECK (duracion_min IS NULL OR duracion_min >= 0),
    observacion    TEXT    NOT NULL CHECK (length(trim(observacion)) > 0)
);
CREATE INDEX IF NOT EXISTS ix_incidencia_fecha ON incidencia (fecha);

CREATE TABLE IF NOT EXISTS configuracion (
    clave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL
);

-- Sesiones de administrador. Solo se guarda el hash del token.
CREATE TABLE IF NOT EXISTS sesion (
    token_hash        TEXT PRIMARY KEY,
    id_administrador  INTEGER NOT NULL REFERENCES administrador (id) ON DELETE CASCADE,
    creada_ts         INTEGER NOT NULL,
    ultimo_uso_ts     INTEGER NOT NULL
);

-- Bitácora: quién hizo qué. No lleva datos personales en `detalle`, solo identificadores.
CREATE TABLE IF NOT EXISTS bitacora (
    id          INTEGER PRIMARY KEY,
    ts          INTEGER NOT NULL,
    actor_tipo  TEXT    NOT NULL CHECK (actor_tipo IN ('administrador', 'operador', 'sistema')),
    actor_id    INTEGER,
    accion      TEXT    NOT NULL,
    entidad     TEXT,
    entidad_id  INTEGER,
    detalle     TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_bitacora_entidad ON bitacora (entidad, entidad_id);

INSERT OR IGNORE INTO tipo_incidencia (id, nombre, requiere_duracion) VALUES
    ('corte-cfe',      'Corte de Energía CFE', 1),
    ('falla-energia',  'Falla en el sistema de Energía interno', 1),
    ('falla-equipo',   'Falla de equipo', 1),
    ('pauta-rtc',      'Sustitución de pauta RTC', 0),
    ('pauta-ine',      'Sustitución de pauta INE', 0),
    ('ajuste-prog',    'Ajuste de programación', 0),
    ('falla-programa', 'Falla de programa o videoclip', 1),
    ('otro',           'Otro', 1);

INSERT OR IGNORE INTO configuracion (clave, valor) VALUES
    ('tolerancia_retardo_min', '5'),
    ('limite_entrada_min', '10'),
    ('tolerancia_salida_min', '3'),
    ('anticipo_entrada_min', '60'),
    ('rebote_seg', '15'),
    ('gracia_sin_salida_min', '120'),
    ('dias_purga_baja', '30');
