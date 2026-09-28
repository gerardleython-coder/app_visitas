# App Pastoral

Sistema móvil fullstack para gestionar distritos, iglesias, pastores, líderes,
hermanos y visitas pastorales. Este repositorio contiene la especificación
técnica y funcional base; la implementación seguirá [INSTRUCTIONS.md](INSTRUCTIONS.md),
que es la fuente normativa del proyecto.

## Contenido

- [Alcance](#alcance)
- [Arquitectura](#arquitectura)
- [Stack](#stack)
- [Roles y permisos](#roles-y-permisos)
- [Modelo de datos](#modelo-de-datos)
- [Historias de usuario y aceptación](#historias-de-usuario-y-aceptación)
- [API](#api)
- [Seguridad](#seguridad)
- [Pruebas](#pruebas)
- [GitHub Actions](#github-actions)
- [Estructura prevista](#estructura-prevista)
- [Estado del proyecto](#estado-del-proyecto)

## Alcance

La aplicación administra la jerarquía `Distrito -> Iglesia` y los usuarios
operativos asociados. `ADMIN`, `PASTOR` y `LIDER` pueden iniciar sesión;
`HERMANO` es un registro sin credenciales.

Funciones principales:

- Administración territorial de distritos e iglesias.
- Asignación de distrito, iglesia, roles y responsables por `ADMIN`.
- Registro y seguimiento de hermanos.
- Creación, edición, cancelación y reprogramación auditada de visitas.
- Rankings por iglesia y período.
- Notificaciones por correo en segundo plano.

## Arquitectura

Se utilizará Clean Architecture con DDD:

```text
Presentación
  Flutter: Views y BLoCs
  FastAPI: Routers y dependencias HTTP
        |
Aplicación
  Casos de uso, comandos, DTOs y puertos
        |
Dominio
  Entidades, value objects, reglas y errores
        ^
Infraestructura
  PostgreSQL, SQLAlchemy, JWT, Argon2id y correo
```

Los repositorios aíslan la persistencia. Strategy centraliza RBAC, Factory
construye entidades y DTOs, y Command encapsula operaciones de visita y
auditoría.

## Stack

| Capa | Tecnología |
| --- | --- |
| Frontend móvil | Flutter 3.x y Dart |
| Estado | `flutter_bloc` |
| HTTP | Dio o Retrofit |
| Backend | Python 3.11+, FastAPI, Pydantic v2 y `tzdata` para `America/Bogota` |
| Persistencia | PostgreSQL 15+, SQLAlchemy 2.0 asíncrono y Alembic |
| Contraseñas | Argon2id o bcrypt con costo mínimo 12 |
| Autenticación | JWT, access token de 15 minutos y refresh token revocable |
| Pruebas | pytest, pytest-asyncio, bloc_test, mocktail y Flutter test |

## Roles y permisos

Solo `ADMIN` asigna roles, distrito e iglesia. Cada pastor y líder pertenece a
una única iglesia activa. Una iglesia puede tener varios pastores y líderes;
`ADMIN` marca como máximo un pastor principal.

| Recurso | ADMIN | PASTOR | LIDER | HERMANO |
| --- | --- | --- | --- | --- |
| Distritos e iglesias | CRUD global | - | - | - |
| Pastores | CRUD y asignación global | - | - | - |
| Líderes | CRUD y asignación global | Consultar y editar datos en su iglesia | Consultar perfil | - |
| Hermanos | CRUD global | CRUD en su iglesia | CRUD de asignados | - |
| Visitas | CRUD global | CRUD en su iglesia | CRUD de asignadas | - |
| Eliminar hermanos y visitas | Sí | Sí, en su alcance | Sí, de asignados | No |
| Rankings | Globales | De su iglesia | - | - |
| Historial de visitas | Consultar | Consultar su iglesia | Estado actual asignado | - |

El backend debe validar siempre el rol, alcance y estado activo. La interfaz no
puede ser la única barrera de autorización. Las operaciones `DELETE` sobre
usuarios, hermanos y visitas aplican desactivación lógica o cierre controlado;
no eliminan físicamente información que sea necesaria para la auditoría.

## Modelo de datos

```text
distritos 1 --- N iglesias
iglesias 1 --- N usuarios
usuarios 1 --- N visitas como líder
usuarios 1 --- N visitas como hermano
usuarios 1 --- N usuarios como líder asignado a hermanos
usuarios (HERMANO) 1 --- N asignaciones_hermano
usuarios (LIDER) 1 --- N asignaciones_hermano
visitas 1 --- N visita_historial
usuarios e iglesias 1 --- N auditoria (actor y alcance territorial)
```

Los únicos estados de visita son `PROGRAMADA`, `COMPLETADA` y `CANCELADA`.
Reprogramar actualiza la fecha de una visita programada y crea una entrada de
historial; no es un estado.

### Tipos y tablas principales

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE rol_usuario AS ENUM ('ADMIN', 'PASTOR', 'LIDER', 'HERMANO');
CREATE TYPE estado_visita AS ENUM ('PROGRAMADA', 'COMPLETADA', 'CANCELADA');
CREATE TYPE tipo_visita AS ENUM (
    'EVANGELISMO',
    'ENSENANZA',
    'CUIDADO_PASTORAL'
);
```

```sql
CREATE TABLE distritos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE iglesias (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    distrito_id UUID NOT NULL REFERENCES distritos(id) ON DELETE RESTRICT,
    nombre VARCHAR(150) NOT NULL,
    direccion TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (distrito_id, nombre)
);

CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    distrito_id UUID REFERENCES distritos(id) ON DELETE RESTRICT,
    iglesia_id UUID REFERENCES iglesias(id) ON DELETE RESTRICT,
    lider_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    telefono VARCHAR(30),
    direccion TEXT,
    email VARCHAR(150) UNIQUE,
    password_hash VARCHAR(255),
    rol rol_usuario NOT NULL DEFAULT 'HERMANO',
    es_pastor_principal BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (es_pastor_principal = FALSE OR rol = 'PASTOR'),
    CHECK (
        rol = 'HERMANO'
        OR (email IS NOT NULL AND password_hash IS NOT NULL)
    ),
    CHECK (
        rol <> 'HERMANO'
        OR (
            telefono IS NOT NULL
            AND direccion IS NOT NULL
            AND distrito_id IS NOT NULL
            AND iglesia_id IS NOT NULL
            AND lider_id IS NOT NULL
        )
    ),
    CHECK (
        rol NOT IN ('PASTOR', 'LIDER')
        OR (distrito_id IS NOT NULL AND iglesia_id IS NOT NULL)
    )
);

CREATE TABLE visitas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lider_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    hermano_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    tipo tipo_visita NOT NULL,
    fecha_programada TIMESTAMPTZ NOT NULL,
    fecha_completada TIMESTAMPTZ,
    duracion_minutos INTEGER NOT NULL CHECK (duracion_minutos > 0),
    ubicacion TEXT NOT NULL,
    observaciones TEXT NOT NULL,
    estado estado_visita NOT NULL DEFAULT 'PROGRAMADA',
    motivo_cancelacion TEXT,
    creado_por UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (estado = 'CANCELADA' AND motivo_cancelacion IS NOT NULL)
        OR (estado <> 'CANCELADA' AND motivo_cancelacion IS NULL)
    ),
    CHECK (
        (estado = 'COMPLETADA' AND fecha_completada IS NOT NULL)
        OR (estado <> 'COMPLETADA' AND fecha_completada IS NULL)
    )
);

CREATE UNIQUE INDEX uq_pastor_principal_por_iglesia
    ON usuarios (iglesia_id)
    WHERE rol = 'PASTOR'
      AND es_pastor_principal = TRUE
      AND activo = TRUE;

CREATE UNIQUE INDEX uq_visita_programada_hermano_fecha
    ON visitas (hermano_id, fecha_programada)
    WHERE estado = 'PROGRAMADA';

CREATE TABLE visita_historial (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    visita_id UUID NOT NULL REFERENCES visitas(id) ON DELETE RESTRICT,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    accion VARCHAR(30) NOT NULL,
    estado_anterior estado_visita,
    estado_nuevo estado_visita,
    fecha_anterior TIMESTAMPTZ,
    fecha_nueva TIMESTAMPTZ,
    datos_anteriores JSONB,
    datos_nuevos JSONB,
    motivo TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sesiones_refresh (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    reemplazado_por UUID REFERENCES sesiones_refresh(id) ON DELETE SET NULL,
    expira_at TIMESTAMPTZ NOT NULL,
    revocado_at TIMESTAMPTZ,
    usado_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE asignaciones_hermano (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hermano_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    lider_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    asignado_por UUID REFERENCES usuarios(id) ON DELETE RESTRICT,
    fecha_asignacion TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    fecha_fin TIMESTAMPTZ
);

CREATE UNIQUE INDEX uq_asignacion_vigente_hermano
    ON asignaciones_hermano (hermano_id)
    WHERE fecha_fin IS NULL;

CREATE TABLE tokens_recuperacion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expira_at TIMESTAMPTZ NOT NULL,
    usado_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE auditoria (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    recurso VARCHAR(50) NOT NULL,
    recurso_id UUID NOT NULL,
    accion VARCHAR(50) NOT NULL,
    iglesia_id UUID REFERENCES iglesias(id) ON DELETE RESTRICT,
    datos_anteriores JSONB,
    datos_nuevos JSONB,
    motivo TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_auditoria_iglesia_fecha
    ON auditoria (iglesia_id, created_at);

CREATE INDEX ix_auditoria_recurso
    ON auditoria (recurso, recurso_id, created_at);

CREATE TABLE notificaciones_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    visita_id UUID NOT NULL REFERENCES visitas(id) ON DELETE RESTRICT,
    destinatario_email VARCHAR(150) NOT NULL,
    tipo VARCHAR(40) NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE'
        CHECK (estado IN ('PENDIENTE', 'PROCESANDO', 'ENVIADA')),
    intentos INTEGER NOT NULL DEFAULT 0,
    ultimo_error VARCHAR(100),
    reintentar_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    bloqueado_hasta TIMESTAMPTZ,
    ultimo_intento_at TIMESTAMPTZ,
    enviado_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (visita_id, destinatario_email, tipo)
);

CREATE INDEX ix_notificacion_outbox_estado_reintento
    ON notificaciones_outbox (estado, reintentar_at);
```

Las reglas de rol, pertenencia a la misma iglesia, distrito coincidente,
fechas y visitas duplicadas deben validarse en dominio, aplicación y
persistencia. Las migraciones deben añadir restricciones o triggers para
impedir que un hermano tenga un líder de otra iglesia o con rol distinto de
`LIDER`. Las fechas relativas a `America/Bogota` se validan en dominio y
aplicación, porque no deben depender de un `CHECK` con tiempo actual. Las
migraciones Alembic serán la fuente de verdad ejecutable.

`asignaciones_hermano` conserva cada líder responsable, quién hizo la asignación
y sus fechas. Reasignar o desactivar un hermano cierra la asignación vigente; no
se sobrescribe su historial.

Las visitas nuevas siempre inician `PROGRAMADA`. El índice parcial evita
duplicar hermano y fecha mientras la visita siga programada. Cada cambio añade
un snapshot JSONB al historial; PostgreSQL impide borrar visitas físicamente o
modificar/eliminar eventos de auditoría. `auditoria` conserva el actor y un
snapshot `iglesia_id` para filtrar el alcance aunque cambie la asignación actual;
un trigger PostgreSQL rechaza `UPDATE` y `DELETE`. `tzdata` suministra
`America/Bogota` en plataformas, como Windows, que no incluyen la base IANA del
sistema.

## Historias de usuario y aceptación

Las historias siguientes son el alcance funcional inicial. Cada historia debe
ser independiente, negociable, valiosa, estimable, pequeña y verificable
(INVEST). Los criterios se expresan en Gherkin y deben convertirse en pruebas
automatizadas antes de implementar el caso de uso.

### HU-01: Autenticación de usuarios operativos

**Como** `ADMIN`, `PASTOR` o `LIDER`, **quiero** iniciar sesión de forma
segura, **para** acceder únicamente a las funciones de mi rol.

```gherkin
Característica: Inicio de sesión

    Escenario: Inicio de sesión válido
        Dado un usuario activo con rol ADMIN, PASTOR o LIDER
        Y sus credenciales son válidas
        Cuando solicita iniciar sesión
        Entonces recibe un access token con duración de 15 minutos
        Y recibe un refresh token rotativo y revocable

    Escenario: Hermano sin acceso
        Dado un registro con rol HERMANO
        Cuando intenta iniciar sesión
        Entonces la solicitud es rechazada
        Y no se emite ningún token

    Escenario: Credenciales inválidas
        Dado un usuario operativo activo
        Cuando presenta una contraseña incorrecta
        Entonces recibe un error de autenticación
        Y el sistema no revela si el email existe
```

### HU-02: Asignación territorial y de roles

**Como** `ADMIN`, **quiero** crear y asignar pastores y líderes a un distrito
y una iglesia, **para** conservar la jerarquía territorial.

```gherkin
Característica: Asignación administrativa

    Escenario: Crear pastor con ubicación válida
        Dado un distrito y una iglesia perteneciente a ese distrito
        Cuando ADMIN crea un pastor y selecciona ambos
        Entonces el pastor queda activo con rol PASTOR
        Y queda asociado al distrito y a la iglesia seleccionados

    Escenario: Crear líder con ubicación válida
        Dado un distrito y una iglesia perteneciente a ese distrito
        Cuando ADMIN crea un líder y selecciona ambos
        Entonces el líder queda activo con rol LIDER
        Y queda asociado al distrito y a la iglesia seleccionados

    Escenario: Intento de asignación por un pastor o líder
        Dado un usuario con rol PASTOR o LIDER
        Cuando intenta asignar un rol
        Entonces la operación es rechazada con ForbiddenException
        Y no se modifica ningún usuario

    Escenario: Iglesia fuera del distrito seleccionado
        Dado un distrito y una iglesia perteneciente a otro distrito
        Cuando ADMIN intenta asignarlos juntos
        Entonces la operación es rechazada
        Y no se crea la asignación

    Escenario: Definir pastor principal
        Dado una iglesia con varios pastores activos
        Cuando ADMIN marca un pastor como principal
        Entonces ese pastor queda como destinatario principal de notificaciones
        Y ningún otro pastor queda marcado como principal en esa iglesia

    Escenario: Impedir desactivar al único pastor principal
        Dado una iglesia con un único pastor principal activo
        Cuando ADMIN intenta desactivarlo sin asignar un reemplazo
        Entonces la operación es rechazada
        Y la iglesia conserva un pastor principal activo
```

### HU-03: Gestión de hermanos

**Como** usuario autorizado, **quiero** administrar los datos de los hermanos
dentro de mi alcance, **para** mantener actualizada la cobertura pastoral.

```gherkin
Característica: Gestión de hermanos

    Escenario: Crear hermano con asignación completa
        Dado un usuario autorizado y un líder activo de la misma iglesia
        Cuando registra nombre, apellido, teléfono, dirección, distrito, iglesia
        Y asigna el hermano al líder
        Entonces se crea un registro HERMANO activo sin credenciales

    Escenario: Crear hermano como líder
        Dado un LIDER activo y asignado a una iglesia
        Cuando registra un hermano de su iglesia sin indicar otro líder
        Entonces el hermano queda asignado al líder autenticado
        Y no se crean email ni contraseña para el hermano

    Escenario: Rechazar líder de otra iglesia
        Dado un hermano y un líder activo de otra iglesia
        Cuando ADMIN o PASTOR intenta asignarlos
        Entonces la operación es rechazada
        Y el hermano conserva su asignación anterior

    Escenario: Líder gestiona un hermano asignado
        Dado un LIDER y un hermano asignado a ese líder
        Cuando el líder consulta, edita o desactiva lógicamente el hermano
        Entonces la operación es permitida

    Escenario: Líder intenta gestionar un hermano no asignado
        Dado un LIDER y un hermano asignado a otro líder
        Cuando intenta consultar, editar o desactivar el hermano
        Entonces la operación es rechazada

    Escenario: Líder intenta cambiar la asignación
        Dado un hermano asignado a un LIDER
        Cuando ese LIDER intenta asignarlo a otro líder
        Entonces la operación es rechazada

    Escenario: Reasignación de líder
        Dado un hermano activo y dos líderes de la misma iglesia
        Cuando ADMIN o PASTOR reasigna el hermano
        Entonces cambia el líder responsable
        Y se conserva la trazabilidad de la asignación
        Y el historial registra el actor, el líder anterior y el nuevo

    Escenario: Desactivar hermano sin borrar relaciones
        Dado un hermano con asignaciones históricas
        Cuando un usuario autorizado lo desactiva
        Entonces queda inactivo
        Y sus asignaciones históricas permanecen consultables
```

### HU-04: Gestión de visitas

**Como** usuario autorizado, **quiero** registrar y administrar visitas de mi
alcance, **para** dar seguimiento a la atención pastoral.

```gherkin
Característica: Gestión del ciclo de vida de una visita

    Escenario: Crear visita programada
        Dado un usuario autorizado y un hermano de su alcance
        Y no existe otra visita programada para el mismo hermano, fecha y hora
        Cuando registra tipo, fecha, duración, ubicación y observaciones
        Entonces se crea una visita con estado PROGRAMADA
        Y se registra la acción en el historial

    Escenario: Bloquear visita duplicada
        Dado una visita PROGRAMADA para un hermano, fecha y hora determinados
        Cuando se intenta crear otra visita con los mismos datos
        Entonces la operación es rechazada
        Y la visita original permanece sin cambios

    Escenario: Completar visita
        Dado una visita PROGRAMADA cuya fecha no es futura
        Cuando un usuario autorizado la marca como COMPLETADA
        Entonces se registra fecha_completada
        Y se registra la transición en el historial

    Escenario: Cancelar visita
        Dado una visita PROGRAMADA
        Cuando un usuario autorizado la cancela con un motivo
        Entonces queda en estado CANCELADA
        Y el motivo queda guardado en el historial

    Escenario: Rechazar cancelación sin motivo
        Dado una visita PROGRAMADA
        Cuando un usuario autorizado intenta cancelarla sin motivo
        Entonces la operación es rechazada
        Y la visita permanece PROGRAMADA

    Escenario: Reprogramar visita
        Dado una visita PROGRAMADA
        Cuando un usuario autorizado cambia su fecha a una fecha futura válida
        Entonces la visita continúa en estado PROGRAMADA
        Y se guarda la fecha anterior y la nueva en el historial

    Escenario: Impedir modificación de visita completada
        Dado una visita COMPLETADA
        Cuando un PASTOR o LIDER intenta modificarla
        Entonces la operación es rechazada
        Y la visita permanece sin cambios

    Escenario: Impedir visita programada en el pasado
        Dado la fecha y hora actuales de America/Bogota
        Cuando se intenta crear una visita PROGRAMADA en el pasado
        Entonces la operación es rechazada

    Escenario: Impedir reprogramación a una fecha pasada
        Dado una visita PROGRAMADA
        Cuando se intenta reprogramar a una fecha anterior a la hora actual de America/Bogota
        Entonces la operación es rechazada

    Escenario: Impedir visita completada en el futuro
        Dado una visita PROGRAMADA con fecha futura
        Cuando se intenta marcarla como COMPLETADA antes de su fecha
        Entonces la operación es rechazada

    Escenario: Impedir reactivación de visita cancelada
        Dado una visita CANCELADA con motivo registrado
        Cuando se intenta completarla o reprogramarla
        Entonces la operación es rechazada
        Y la visita permanece CANCELADA
```

### HU-05: Auditoría de visitas y gestión

**Como** `ADMIN` o `PASTOR`, **quiero** consultar el historial de visitas y los
cambios de gestión, **para** verificar quién realizó cada operación dentro de
mi alcance.

```gherkin
Característica: Historial de auditoría

    Escenario: Consultar historial permitido
        Dado una visita dentro del alcance del usuario
        Y el usuario tiene rol ADMIN o PASTOR
        Cuando consulta el historial
        Entonces observa actor, fecha, acción, estados, fechas y motivo

    Escenario: Ocultar historial al líder
        Dado un LIDER con una visita asignada
        Cuando consulta el historial de la visita
        Entonces la operación es rechazada
        Y solo puede consultar el estado actual

    Escenario: Impedir historial fuera de alcance
        Dado un PASTOR y una visita de otra iglesia
        Cuando consulta el historial de esa visita
        Entonces la operación es rechazada

    Escenario: Consultar auditoría global
        Dado un ADMIN autenticado
        Cuando consulta la auditoría de asignaciones y desactivaciones
        Entonces puede consultar eventos de cualquier distrito e iglesia

    Escenario: Consultar cambios de gestión sin exponer credenciales
        Dado eventos de creación, modificación, reasignación y desactivación
        Cuando ADMIN o PASTOR consulta la auditoría dentro de su alcance
        Entonces observa actor, recurso, acción, valores anteriores y nuevos
        Y no se exponen passwords, hashes ni tokens

    Escenario: Denegar auditoría global a un líder
        Dado un LIDER autenticado
        Cuando consulta la auditoría
        Entonces la operación es rechazada
```

### HU-06: Notificaciones de visita

**Como** responsable pastoral, **quiero** recibir aviso al crear o agendar una
visita, **para** coordinar su seguimiento.

```gherkin
Característica: Notificación de visita

    Escenario: Notificar una nueva visita
        Dado una visita creada correctamente
        Y existe un líder responsable y un pastor principal activo
        Cuando finaliza la transacción de persistencia
        Entonces se encola un correo para el líder
        Y se encola un correo para el pastor principal
        Y el envío inicia después del commit

    Escenario: Reintentar una notificación fallida
        Dado una notificación pendiente y una visita confirmada
        Cuando el servidor SMTP rechaza la entrega
        Entonces la visita permanece confirmada
        Y se registra el intento fallido sin guardar credenciales
        Y la notificación queda pendiente con una fecha de reintento
        Y un worker vuelve a intentar la entrega cuando vence esa fecha
```

### HU-07: Ranking de líderes

**Como** `ADMIN` o `PASTOR`, **quiero** consultar el ranking de mi alcance,
**para** conocer la actividad de visitas completadas.

```gherkin
Característica: Ranking de líderes

    Escenario: Ranking mensual por iglesia
        Dado una iglesia y el período MES
        Y existen visitas COMPLETADA asociadas a sus líderes
        Cuando se solicita el ranking
        Entonces solo se cuentan visitas COMPLETADA del período
        Y se agrupa por líder
        Y se ordena con DENSE_RANK descendente por cantidad

    Escenario: Empate de líderes
        Dado dos líderes con la misma cantidad de visitas COMPLETADA
        Cuando se calcula el ranking
        Entonces ambos reciben la misma posición

    Escenario: Ranking semanal usa el calendario de Bogota
        Dado visitas completadas de líderes de una iglesia
        Y el período solicitado es SEMANA con una fecha de referencia
        Cuando ADMIN o PASTOR consulta el ranking
        Entonces se incluyen las visitas completadas desde el lunes a las 00:00
        Y se excluyen las visitas desde el lunes siguiente a las 00:00

    Escenario: Limitar ranking a la iglesia del pastor
        Dado un PASTOR con una iglesia activa asignada
        Cuando solicita un ranking de otra iglesia
        Entonces la operación es rechazada

    Escenario: Denegar ranking a un líder
        Dado un LIDER autenticado
        Cuando solicita un ranking
        Entonces la operación es rechazada
```

### HU-08: Sesiones y recuperación de cuenta

**Como** usuario operativo, **quiero** renovar o recuperar mi acceso,
**para** mantener la continuidad y seguridad de mi cuenta.

```gherkin
Característica: Seguridad de sesión

    Escenario: Renovar sesión
        Dado un refresh token vigente y no revocado
        Cuando solicita renovar la sesión
        Entonces recibe un nuevo access token
        Y el refresh token anterior queda invalidado

    Escenario: Cerrar sesión
        Dado una sesión activa
        Cuando el usuario cierra sesión
        Entonces el refresh token queda revocado
        Y no puede reutilizarse

    Escenario: Restablecer contraseña
        Dado un email perteneciente a un usuario con acceso
        Cuando solicita y confirma el restablecimiento
        Entonces la contraseña se actualiza con un hash seguro
        Y los refresh tokens anteriores quedan revocados

    Escenario: Solicitar recuperación sin revelar si existe la cuenta
        Dado un email de una cuenta operativa o un email desconocido
        Cuando solicita recuperar la contraseña
        Entonces ambas solicitudes reciben la misma respuesta
        Y ningún token se incluye en la respuesta HTTP

    Escenario: Rechazar token de recuperación expirado o reutilizado
        Dado un token de recuperación vencido o previamente consumido
        Cuando intenta restablecer la contraseña
        Entonces la operación es rechazada con un error genérico
        Y la contraseña y las sesiones no cambian

    Escenario: Cambiar contraseña con sesión autenticada
        Dado un usuario operativo activo con su contraseña actual
        Cuando cambia la contraseña autenticado
        Entonces la contraseña se almacena con Argon2
        Y todas sus sesiones refresh quedan revocadas

    Escenario: Rechazar cambio con contraseña actual incorrecta
        Dado un usuario operativo autenticado
        Cuando presenta una contraseña actual incorrecta
        Entonces recibe un error genérico de autenticación
        Y la contraseña y sesiones no cambian

    Escenario: Impedir reutilización de refresh token
        Dado un refresh token que ya fue utilizado o revocado
        Cuando se intenta renovar la sesión con ese token
        Entonces la operación es rechazada
        Y la sesión asociada queda invalidada
```

### HU-09: Desactivación y conservación del historial

**Como** usuario autorizado, **quiero** desactivar usuarios o hermanos dentro
de mi alcance sin borrar sus relaciones históricas, **para** conservar la
trazabilidad pastoral.

```gherkin
Característica: Desactivación lógica

    Escenario: Desactivar un hermano
        Dado un hermano con visitas e historial existentes
        Cuando un usuario con permiso lo desactiva
        Entonces el hermano queda inactivo
        Y sus visitas e historial permanecen consultables según permisos
        Y el hermano no puede recibir nuevas visitas

    Escenario: Desactivar un usuario operativo
        Dado un PASTOR o LIDER con una cuenta activa
        Cuando ADMIN lo desactiva
        Entonces no puede iniciar sesión
        Y sus acciones históricas conservan su identidad
        Y no se borran los registros relacionados
```

### HU-10: Administración territorial

**Como** `ADMIN`, **quiero** administrar distritos e iglesias sin perder sus
relaciones históricas, **para** mantener vigente la estructura territorial.

```gherkin
Característica: Administración territorial

    Escenario: Administrar un distrito sin iglesias
        Dado un usuario ADMIN autenticado
        Cuando crea, renombra y elimina un distrito sin iglesias
        Entonces cada cambio queda auditado

    Escenario: Impedir eliminar un distrito con iglesias
        Dado un distrito que tiene iglesias asociadas
        Cuando ADMIN intenta eliminarlo
        Entonces recibe un conflicto
        Y el distrito y sus iglesias permanecen sin cambios

    Escenario: Administrar una iglesia sin moverla de distrito
        Dado una iglesia activa
        Cuando ADMIN actualiza su nombre o dirección
        Entonces sus datos cambian
        Y permanece en el distrito original

    Escenario: Desactivar una iglesia sin usuarios activos
        Dado una iglesia sin usuarios activos
        Cuando ADMIN la elimina
        Entonces queda inactiva sin borrar su historial ni relaciones

    Escenario: Impedir desactivar una iglesia con usuarios activos
        Dado una iglesia con usuarios activos
        Cuando ADMIN intenta eliminarla
        Entonces recibe un conflicto
        Y la iglesia permanece activa

    Escenario: Denegar gestión territorial a PASTOR y LIDER
        Dado un usuario autenticado con rol PASTOR o LIDER
        Cuando intenta consultar o modificar distritos o iglesias
        Entonces recibe una respuesta de permisos insuficientes
        Y no se modifica ningún registro
```

### Criterios de diseño para las HU

- **INVEST:** cada HU debe tener un único valor de negocio, alcance acotado,
    criterios observables y poder probarse de forma independiente.
- **SOLID:** las HU se implementan mediante casos de uso pequeños, puertos
    para repositorios y correo, estrategias RBAC separadas y entidades de
    dominio sin dependencias de frameworks.
- Los escenarios Gherkin describen comportamiento observable; no deben acoplarse
    a tablas, clases o detalles internos de implementación.

## API

Prefijo: `/api/v1`.

| Método y ruta | Alcance |
| --- | --- |
| `POST /auth/login` | ADMIN, PASTOR o LIDER |
| `POST /auth/refresh` | Rotar refresh token de un solo uso |
| `POST /auth/logout` | Revocar sesión y refresh token |
| `POST /auth/password/forgot` | 202 neutral; envía token de recuperación solo a cuentas operativas existentes |
| `POST /auth/password/reset` | Consume token de un uso; actualiza password y revoca todas las sesiones |
| `POST /auth/password/change` | ADMIN, PASTOR o LIDER autenticado; verifica contraseña actual y revoca refresh |
| `GET /admin/distritos` | ADMIN |
| `POST /admin/distritos` | ADMIN |
| `PATCH /admin/distritos/{id}` | ADMIN, actualiza nombre |
| `DELETE /admin/distritos/{id}` | ADMIN, solo si no tiene iglesias asociadas |
| `GET /admin/iglesias` | ADMIN |
| `POST /admin/iglesias` | ADMIN |
| `PATCH /admin/iglesias/{id}` | ADMIN, actualiza nombre/dirección; distrito inmutable |
| `PATCH /admin/iglesias/{id}/pastor-principal` | ADMIN, definir un único pastor principal |
| `DELETE /admin/iglesias/{id}` | ADMIN, desactivación lógica; requiere cero usuarios activos |
| `GET /users/pastores` | ADMIN |
| `POST /users/pastores` | ADMIN, crea y asigna |
| `PATCH /users/pastores/{id}` | ADMIN |
| `DELETE /users/pastores/{id}` | ADMIN, desactivación lógica |
| `GET /users/lideres` | ADMIN o PASTOR en alcance |
| `POST /users/lideres` | ADMIN, crea y asigna |
| `PATCH /users/lideres/{id}` | ADMIN o PASTOR en alcance |
| `DELETE /users/lideres/{id}` | ADMIN o PASTOR en alcance |
| `GET /hermanos` | Según alcance |
| `POST /hermanos` | ADMIN, PASTOR o LIDER autorizado |
| `GET /hermanos/{id}` | Según alcance |
| `PATCH /hermanos/{id}` | Según alcance |
| `DELETE /hermanos/{id}` | ADMIN, PASTOR o LIDER asignado |
| `PATCH /hermanos/{id}/lider` | ADMIN o PASTOR |
| `GET /visitas` | Según alcance |
| `POST /visitas` | ADMIN, PASTOR o LIDER autorizado |
| `GET /visitas/{id}` | Según alcance |
| `PATCH /visitas/{id}` | Según rol y estado |
| `DELETE /visitas/{id}` | ADMIN, PASTOR o LIDER asignado; cancela con motivo, sin borrar |
| `GET /visitas/{id}/history` | ADMIN o PASTOR en alcance |
| `GET /audit?offset=0&limit=100` | ADMIN global o PASTOR dentro de su iglesia; paginado, `limit` máximo 500 |
| `GET /reports/ranking?period=SEMANA\|MES&church_id=...&reference_date=YYYY-MM-DD` | ADMIN indica iglesia; PASTOR queda limitado a la suya |

Todos los endpoints protegidos deben verificar autenticación, rol, iglesia,
propiedad o asignación, y devolver errores HTTP consistentes.

`POST /visitas` recibe `brother_id`, `visit_type`, `scheduled_at` con zona,
`duration_minutes`, `location` y `observations`; líder y creador se derivan de
la cuenta y asignación vigentes. `PATCH /visitas/{id}` actualiza esos datos o
marca `status: COMPLETADA`; para cancelar se usa `DELETE` con `{ "reason":
"..." }`. Reprogramar conserva `PROGRAMADA` y cambia `scheduled_at`.

Para `POST /hermanos`, ADMIN y PASTOR deben enviar `leader_id`; LIDER puede
omitirlo y el backend asigna al líder autenticado. `PATCH /hermanos/{id}` solo
actualiza nombre, apellido, teléfono y dirección. La reasignación usa
`PATCH /hermanos/{id}/lider` y solo permite ADMIN o PASTOR; el distrito y la
iglesia permanecen inmutables para conservar las relaciones históricas.

## Seguridad

Crear `backend/.env` localmente y no versionarlo. Estos valores son
placeholders, no credenciales de producción:

```dotenv
PROJECT_NAME=app-pastoral-api
DATABASE_URL=postgresql+asyncpg://usuario:CONTRASENA@localhost:5432/app_pastoral
SECRET_KEY=generar-un-secreto-largo-fuera-del-repositorio
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
TIMEZONE=America/Bogota
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=usuario-smtp
SMTP_PASSWORD=secreto-smtp
SMTP_USE_TLS=true
EMAILS_FROM_EMAIL=no-reply@example.com
```

Las contraseñas se almacenan únicamente mediante Argon2id o bcrypt. Los
refresh tokens se rotan, revocan al cerrar sesión y expiran automáticamente.
La configuración SMTP usa secretos del entorno; nunca se incluyen credenciales
reales en este archivo.

## Pruebas

El desarrollo sigue **RED -> GREEN -> REFACTOR**.

Backend:

```bash
cd backend
RUN_POSTGRES_INTEGRATION=1 poetry run pytest --cov=app --cov-report=term-missing --cov-fail-under=91
```

Frontend:

```bash
cd frontend
flutter test --coverage
```

La cobertura mínima objetivo es del 91 %. Deben cubrirse autorización,
asignaciones, fechas, duplicados, transiciones, auditoría, ranking, BLoCs,
widgets y notificaciones desacopladas.

## GitHub Actions

El workflow [Backend CI](.github/workflows/backend-ci.yml) ejecuta Ruff y pytest
con cobertura mínima del 91 % para Python 3.11 y 3.12 en cada push y pull
request dirigido a `main`.

## Estructura prevista

```text
app-pastoral/
├── .github/workflows/
├── backend/
│   ├── app/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── presentation/
│   ├── tests/
│   ├── alembic.ini
│   ├── migrations/
│   ├── Dockerfile
│   └── pyproject.toml
└── frontend/
    ├── lib/
    │   ├── core/
    │   ├── features/
    │   └── main.dart
    ├── test/
    └── pubspec.yaml
```

## Estado del proyecto

El backend tiene las rutas `POST /api/v1/auth/login` y
`POST /api/v1/auth/refresh`, con Argon2id, access JWT de 15 minutos, refresh
hasheado y rotación de una sola vez; la reutilización revoca la familia. HU-02
incluye creación, consulta, edición y desactivación lógica de pastores y líderes,
con autorización por rol y alcance de iglesia. ADMIN puede asignar el pastor
principal; la aplicación y un trigger PostgreSQL impiden desactivar al único
principal activo sin reemplazo. Las migraciones validan la relación territorial
y el estado de las iglesias. HU-03 implementa CRUD de hermanos según alcance,
reasignación de líder por ADMIN/PASTOR y conservación del historial; las
migraciones impiden asignar líderes de otro rol o iglesia. El esquema está
aplicado en PostgreSQL 17 local. HU-04 implementa el ciclo de visitas, alcance
por rol, rechazo de duplicados, validación horaria en `America/Bogota` e historial
append-only; PostgreSQL protege asignaciones, unicidad y borrado físico. GitHub
Actions usa PostgreSQL 17 efímero para migraciones e integración. HU-05
implementa auditoría append-only de creación, modificación, reasignación,
asignación de pastor principal y desactivación; `GET /api/v1/audit` aplica
scope global ADMIN o scope de iglesia PASTOR con paginación, y PostgreSQL
rechaza modificaciones y borrados directos. HU-06 encola notificaciones
transaccionales para el líder y el pastor principal, las envía después del
commit mediante SMTP y deja fallos en un outbox durable con backoff, contador de
intentos y tipo de error; un worker del lifespan reintenta mensajes vencidos
cada 30 segundos. HU-07 implementa ranking por iglesia con `DENSE_RANK()` de
visitas completadas por `fecha_completada`, periodos de semana/mes en
`America/Bogota` y scope ADMIN/PASTOR. HU-08 implementa recuperación con token
aleatorio de 30 minutos almacenado como SHA-256, respuesta anti-enumeración,
consumo de un uso y revocación de refresh tokens al cambiar la contraseña.
HU-09 verifica desactivación lógica de hermanos y operadores, historial de
visitas y asignaciones preservado, bloqueo de nuevas visitas y rechazo de login
para cuentas inactivas. El CRUD territorial ADMIN protege dependencias con
conflictos y desactiva iglesias sin borrar historia; el cambio autenticado de
contraseña verifica el valor actual y revoca sesiones refresh. El frontend
Flutter sigue pendiente. Se mantiene `INSTRUCTIONS.md` como contrato funcional y
se implementa en iteraciones TDD.