# Instrucciones técnicas y reglas de negocio

## 1. Rol y objetivo

Actúa como Arquitecto de Software Fullstack Senior, con experiencia en Flutter,
Python, FastAPI, PostgreSQL, Clean Architecture, DDD, SOLID y TDD.

El objetivo es construir una aplicación de producción mantenible, segura,
testeable y coherente con este documento, que es la fuente normativa del
proyecto.

## 2. Stack tecnológico oficial

- **Frontend móvil:** Flutter 3.x con Dart, `flutter_bloc` para estado y Dio o
  Retrofit para HTTP.
- **Backend API:** Python 3.11 o superior, FastAPI y Pydantic v2.
- **Base de datos:** PostgreSQL 15 o superior, SQLAlchemy 2.0 asíncrono y
  Alembic.
- **Seguridad:** JWT con access token de corta duración y refresh token
  rotativo y revocable. Contraseñas con Argon2id o bcrypt con costo mínimo 12.
- **Correo:** SMTP o SendGrid mediante tareas en segundo plano de FastAPI.
- **Pruebas:** pytest y pytest-asyncio para backend; bloc_test, mocktail y
  Flutter test para frontend.

## 3. Arquitectura y dependencias

El proyecto debe seguir Clean Architecture y DDD:

1. **Dominio:** entidades, value objects, reglas, errores e interfaces de
   repositorio. No depende de FastAPI, SQLAlchemy, Pydantic ni Flutter.
2. **Aplicación:** casos de uso, comandos, puertos y DTOs de aplicación.
3. **Infraestructura:** repositorios SQLAlchemy, migraciones, seguridad,
   correo, configuración y clientes externos.
4. **Presentación:** routers y dependencias HTTP en FastAPI; BLoCs, pantallas
   y widgets en Flutter.

Las dependencias deben apuntar hacia el dominio. La inyección de dependencias
se realizará en los límites de infraestructura y presentación.

### Patrones obligatorios

- **Repository:** separa el dominio de PostgreSQL, memoria local y HTTP.
- **Observer / Pub-Sub:** BLoC comunica eventos y estados al frontend.
- **Strategy:** encapsula permisos por rol con `AdminStrategy`,
  `PastorStrategy` y `LiderStrategy`.
- **Factory:** construye entidades, DTOs y mapeos entre persistencia y dominio.
- **Command:** encapsula creación, actualización, cancelación y
  reprogramación de visitas para auditoría.

## 4. Reglas de negocio

### Jerarquía y asignaciones

La jerarquía es `Distrito -> Iglesia -> Usuarios -> Hermanos y visitas`.

- Solo `ADMIN` asigna roles, distrito e iglesia.
- `ADMIN` debe seleccionar una iglesia perteneciente al distrito seleccionado.
- Cada `PASTOR` y `LIDER` pertenece a una única iglesia activa y debe tener
  distrito e iglesia asignados.
- Una iglesia puede tener varios pastores y líderes activos.
- `ADMIN` marca como máximo un pastor principal por iglesia para notificaciones.
- Cada `HERMANO` debe tener nombre, apellido, teléfono, dirección, distrito,
  iglesia y un líder asignado.
- El distrito del hermano debe coincidir con el distrito de su iglesia.
- Un hermano puede cambiar de líder solo por `ADMIN` o `PASTOR`.
- Un líder puede tener varios hermanos asignados.
- El cambio de iglesia de un usuario o hermano se realiza mediante
  desactivación de la asignación anterior y creación de una nueva; no se
  mueven silenciosamente las relaciones históricas.

### Roles y acceso

- `ADMIN`, `PASTOR` y `LIDER` tienen acceso a la aplicación.
- `HERMANO` es un registro administrado y nunca tiene credenciales.
- Email y contraseña son obligatorios solo para usuarios con acceso.

### Permisos

| Recurso | ADMIN | PASTOR | LIDER | HERMANO |
| --- | --- | --- | --- | --- |
| Distritos e iglesias | CRUD global | Sin acceso | Sin acceso | Sin acceso |
| Pastores | CRUD y asignación global | Sin acceso | Sin acceso | Sin acceso |
| Líderes | CRUD y asignación global | Consultar y editar datos en su iglesia | Consultar perfil | Sin acceso |
| Hermanos | CRUD global | CRUD en su iglesia | CRUD de asignados | Sin acceso |
| Visitas | CRUD global | CRUD en su iglesia | CRUD de asignadas | Sin acceso |
| Eliminar hermanos y visitas | Sí | Sí, en su alcance | Sí, de asignados | No |
| Reportes y rankings | Globales | De su iglesia | Sin acceso | Sin acceso |

El backend debe comprobar rol, alcance y estado activo en cada operación. La
interfaz no constituye una barrera de autorización.

### Visitas

- Los únicos estados son `PROGRAMADA`, `COMPLETADA` y `CANCELADA`.
- La reprogramación no es un estado: actualiza la fecha de una visita
  `PROGRAMADA` y registra el cambio en el historial.
- `ADMIN`, `PASTOR` y `LIDER` pueden crear visitas para hermanos de su alcance.
- Una visita `PROGRAMADA` puede completarse, cancelarse o reprogramarse.
- Una visita `COMPLETADA` solo puede modificarse por `ADMIN`.
- Una visita `CANCELADA` no puede reactivarse; se crea otra si es necesario.
- Cancelar requiere registrar un motivo.
- `DELETE /visitas/{id}` equivale a cancelar con motivo e historial; nunca se
  elimina físicamente una visita.
- No se permiten visitas programadas duplicadas para el mismo hermano, fecha y
  hora.
- Una visita registra tipo, fecha, duración, ubicación y observaciones.
- Los tipos son `EVANGELISMO`, `ENSENANZA` y `CUIDADO_PASTORAL`.
- No se permite una visita programada en el pasado ni una completada en el
  futuro.

### Auditoría

Debe conservarse historial de quién creó, modificó, completó, canceló o
reprogramó una visita, cuándo ocurrió, el estado anterior y el nuevo, los
valores relevantes y el motivo cuando corresponda. `ADMIN` y `PASTOR` pueden
consultar el historial; `LIDER` solo consulta el estado actual de sus registros.

### Rankings

El ranking se calcula por iglesia y período (`SEMANA` o `MES`), contando solo
visitas `COMPLETADA`. La posición se obtiene con `DENSE_RANK()`, por lo que los
empates comparten posición. El conteo usa `fecha_completada`; `SEMANA` empieza
el lunes a las 00:00 y termina el lunes siguiente, y `MES` empieza el primer día
del mes y termina el primer día del mes siguiente. Ambos límites se interpretan
en `America/Bogota`; el inicio es inclusivo y el fin exclusivo. ADMIN debe
indicar una iglesia; PASTOR consulta únicamente la iglesia activa asignada.

### Notificaciones

Al crear o agendar una visita se notifica en segundo plano al líder responsable
del hermano y al pastor principal de la iglesia. El fallo del correo no deshace
la operación confirmada; debe registrarse para reintento y observabilidad.

## 5. Persistencia y seguridad

- Usar UUID y `TIMESTAMP WITH TIME ZONE`.
- Crear explícitamente la extensión PostgreSQL requerida por UUID.
- Validar roles, estados, alcance, pertenencia a iglesia y unicidad de visitas
  en dominio, aplicación y persistencia.
- Los usuarios y hermanos se desactivan lógicamente para conservar historial.
- El access token dura 15 minutos.
- Los refresh tokens se rotan, se almacenan de forma revocable y se invalidan
  al cerrar sesión, expirar o detectar reutilización.
- Debe existir recuperación y cambio de contraseña para usuarios con acceso.
- Los secretos se cargan desde variables de entorno y nunca se versionan.
- No incluir secretos reales, tokens ni credenciales en documentación,
  fixtures o mensajes de error.

## 6. API y contratos

La API usa el prefijo `/api/v1` y debe incluir como mínimo:

- `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`.
- `POST /auth/password/forgot` y `POST /auth/password/reset`.
- CRUD de `/admin/distritos` y `/admin/iglesias`, solo `ADMIN`.
- CRUD y asignación de `/users/pastores`, solo `ADMIN`.
- Creación y asignación de `/users/lideres`, solo `ADMIN`; `PASTOR` puede
  consultar y editar sus datos sin cambiar el rol.
- CRUD de `/hermanos` según alcance; reasignación de líder por `ADMIN` o
  `PASTOR`.
- CRUD de `/visitas` según alcance y reglas de estado.
- `GET /visitas/{id}/history` para `ADMIN` y `PASTOR`.
- `GET /audit` para `ADMIN` global y `PASTOR` dentro de su iglesia.
- `GET /reports/ranking?period=SEMANA|MES&church_id=...&reference_date=YYYY-MM-DD`
  para ADMIN y PASTOR; ADMIN indica iglesia y PASTOR queda limitado a la suya.

Todos los endpoints protegidos deben comprobar autenticación, rol, iglesia,
propiedad o asignación, y devolver errores HTTP consistentes.

## 7. Historias de usuario y criterios de aceptación

Las historias de usuario son el contrato funcional que conecta negocio,
desarrollo y pruebas. Cada HU debe cumplir INVEST:

- **Independent:** puede priorizarse e implementarse sin depender de otra HU,
  salvo dependencias explícitas del dominio.
- **Negotiable:** describe el valor y el comportamiento, no una solución
  técnica cerrada.
- **Valuable:** aporta valor a un rol concreto.
- **Estimable:** tiene alcance y reglas suficientemente claros.
- **Small:** puede completarse en una iteración razonable.
- **Testable:** tiene criterios observables y verificables.

Cada HU debe escribirse con el formato:

`Como [rol], quiero [acción], para [valor].`

Sus criterios deben expresarse en Gherkin usando `Característica`, `Escenario`,
`Dado`, `Cuando`, `Entonces` y `Y`. Los escenarios deben probar resultados
observables, errores de autorización, límites de alcance y reglas de negocio;
no deben describir detalles internos de SQLAlchemy, Flutter o la estructura de
clases.

Las nueve HU funcionales iniciales y sus escenarios completos están en la
sección "Historias de usuario y aceptación" del `README.md`. Deben cubrir
autenticación, asignación administrativa, hermanos, visitas, auditoría,
notificaciones, ranking, recuperación de cuenta y desactivación lógica.

### Relación con SOLID

- **S:** cada caso de uso representa una capacidad de negocio concreta.
- **O:** agregar un rol, notificación o proveedor no debe modificar las reglas
  existentes; usar estrategias y puertos extensibles.
- **L:** las implementaciones de repositorio y servicios deben respetar sus
  contratos.
- **I:** definir interfaces pequeñas para persistencia, correo, tokens y
  auditoría.
- **D:** los casos de uso dependen de abstracciones del dominio, no de FastAPI,
  SQLAlchemy, SendGrid o Flutter.

Una HU se considera terminada únicamente cuando sus escenarios Gherkin pasan,
la autorización se valida en backend y existe cobertura adecuada en dominio,
aplicación y presentación.

## 8. TDD y calidad

El ciclo obligatorio es **RED -> GREEN -> REFACTOR**.

- Backend: pruebas unitarias de dominio y casos de uso, integración HTTP y
  persistencia, con `pytest-asyncio` y cobertura mínima del 85 %.
- Frontend: pruebas de BLoC con `bloc_test`, mocks con `mocktail` y widget
  tests de estados de carga, éxito y error.
- Cubrir autorización, límites de iglesia, asignaciones, transiciones de
  visita, duplicados, auditoría, ranking y notificaciones desacopladas.
- Usar excepciones explícitas como `DomainException`, `UnauthorizedException`
  y `ForbiddenException`. Nunca usar `except:` vacío.

## 9. Formato de entregas

Toda entrega de código debe indicar la ruta relativa del archivo y proporcionar
código completo, ejecutable y coherente con esta especificación. No introducir
dependencias innecesarias ni modificar APIs públicas sin justificarlo.