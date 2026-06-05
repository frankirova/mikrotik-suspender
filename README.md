# IP Suspension Tool — MikroTik + CSV

Automatiza el bloqueo (suspensión) de direcciones IP en un **MikroTik RouterOS** a partir de un **CSV local**. Cada vez que se ejecuta, lee los clientes del CSV, los agrega al address-list `suspendido` del router y activa el bloqueo.

> Diseñada para automatizar la suspensión de clientes morosos en el firewall de manera masiva y sin entrar al router manualmente.

---

## ⚠️ Aviso de seguridad

Por defecto escucha en `127.0.0.1` (únicamente loopback) y asume una red local de confianza. **Soportá autenticación opcional vía Bearer token** (ver [Authentication](#authentication) abajo), pero la deja **desactivada** para no romper el dev local.

**No expongas este servicio directamente a internet sin activar la auth** — cualquier visitante podría:

- Ejecutar cambios en el firewall del MikroTik (suspender / des-suspender IPs arbitrarias).
- Leer y modificar las IPs de opciones almacenadas.
- Leer y modificar el CSV local.

Activá `API_KEY` en tu `.env` antes de exponer el servicio más allá de tu workstation. Para escenarios de producción más estrictos considerá también un reverse proxy con TLS. El diseño original asume que un operador ejecuta la herramienta en su máquina y dispara las suspensiones de forma manual. Ver [TECHNICAL_DEBT.md](./TECHNICAL_DEBT.md) para la lista completa de mejoras planeadas.

---

## Quick path

```bash
# 1. Preparar entorno
cp .env.example .env   # y completar credenciales del MikroTik
pip install -r requirements.txt

# 2. (Opcional) editar la lista de clientes
#    Al primer arranque se crea data/clientes.csv.example automáticamente.
#    Editá data/clientes.csv con tus IPs y nombres (columnas: ip, nombre).

# 3. Iniciar servidor — el bootstrap crea data/, copia el CSV de ejemplo,
#    inicializa la DB SQLite y siembra las opciones por defecto.
uvicorn main:api --reload

# 4. Probar
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/readOptions
```

---

## Cómo funciona

```
┌────────────┐    ┌──────────────┐    ┌──────────────────┐
│  Frontend  │───▶│  FastAPI     │───▶│  CSV local       │
│  (vanilla) │    │  (Python)    │    │  (clientes + IPs) │
└────────────┘    │              │    └──────────────────┘
                  │              │
                  │              │    ┌──────────────────┐
                  │              │───▶│  MikroTik        │
                  │              │    │  (address-list   │
                  │              │    │   'suspendido')  │
                  │              │    └──────────────────┘
                  │              │
                  │              │    ┌──────────────────┐
                  │              │───▶│  SQLite          │
                  │              │    │  (option IPs)    │
                  └──────────────┘    └──────────────────┘
```

### Flujo de suspensión (endpoints `/preview` y `/script`)

1. **Leer CSV** — se lee `data/clientes.csv` y se obtienen los pares `{ip, nombre}`.
2. **Conectar a MikroTik** — usando IP + credenciales del `.env`.
3. **Sincronizar** — para cada IP del CSV que aún no está en el address-list `suspendido`, la agrega con el nombre del cliente como comentario.
4. **Cruzar datos** — busca qué entradas del address-list coinciden con IPs del CSV.
5. **Acción**:
   - `/preview`: devuelve qué se suspendería **sin ejecutar nada**.
   - `/script`: **ejecuta** la suspensión — activa cada entrada (`disabled=false`) y agrega la fecha al comentario.

---

## API Endpoints

| Método | Ruta | Auth | Body | Respuesta | Qué hace |
|--------|------|------|------|-----------|----------|
| `POST` | `/preview` | Bearer | `{IP_MIKROTIK, DATE}` | `[[{id, comment}], [{id, comment}]]` | Muestra qué IPs se suspenderían sin ejecutar |
| `POST` | `/script` | Bearer | `{IP_MIKROTIK, DATE}` | `{"message": "done"}` | Ejecuta la suspensión en el router |
| `POST` | `/addOptions` | Bearer | — | `{"message": "..."}` | Inserta las IPs por defecto en la DB (idempotente) |
| `GET` | `/readOptions` | Bearer | — | `{"data": ["ip1", "ip2"]}` | Lista las IPs guardadas |
| `POST` | `/addDoc` | Bearer | `{"option": "x.x.x.x"}` | `{"message": "..."}` | Agrega una IP a las opciones |
| `GET` | `/health` | — | — | `{"status": "ok"}` | Health check |

### Formato de `/preview`

La respuesta es una lista de **dos sublistas**:

```json
[
  [  ← lista 0: comentarios actuales de las IPs a suspender
    {"id": "*1", "comment": "Cliente A"},
    {"id": "*2", "comment": "Cliente B"}
  ],
  [  ← lista 1: mismos elementos con fecha de suspensión agregada
    {"id": "*1", "comment": "Cliente A// SUSPENDIDO - 2025-01-15"},
    {"id": "*2", "comment": "Cliente B// SUSPENDIDO - 2025-01-15"}
  ]
]
```

### Frontend web (MVP)

Apuntá el navegador a **http://127.0.0.1:8000** y tenés una interfaz lista para:

- **Previsualizar** qué IPs se van a suspender (tabla con comentarios).
- **Ejecutar** la suspensión de un solo clic.
- **Gestionar opciones** — ver y agregar IPs a la lista de opciones guardadas.

```
mikrotik-suspender/
└── static/
    ├── index.html      ← Página principal
    ├── css/style.css   ← Estilos
    └── js/app.js       ← Lógica del frontend
```

> Tip: en `docs/preview-frontend.html` hay una vista estática del UI — abrila en el navegador para ver cómo se ve sin tener que levantar el backend.

El frontend es vanilla JS sin frameworks. Se sirve desde el mismo FastAPI.

### Ejemplos con curl

```bash
# Health check
curl http://127.0.0.1:8000/health

# Preview
curl -X POST http://127.0.0.1:8000/preview \
  -H "Content-Type: application/json" \
  -d '{"IP_MIKROTIK":"192.168.88.1","DATE":"2025-06-01"}'

# Ejecutar
curl -X POST http://127.0.0.1:8000/script \
  -H "Content-Type: application/json" \
  -d '{"IP_MIKROTIK":"192.168.88.1","DATE":"2025-06-01"}'

# Leer opciones guardadas
curl http://127.0.0.1:8000/readOptions
```

---

## Authentication

Los endpoints de la API (todos menos `/health`) requieren un Bearer token **si y solo si** la variable de entorno `API_KEY` está configurada. Si `API_KEY` está vacía o no está definida, la API corre **sin autenticación** y se loguea un WARNING grande al arranque.

**Diseñado así** para que el dev local funcione out-of-the-box. **Activá la auth antes de exponer el servicio más allá de tu workstation**.

### Setup

```bash
# 1. Generá una key segura:
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Pegala en tu .env:
API_KEY=la_key_que_te_dio_el_paso_1

# 3. Reiniciá el servicio. Vas a ver el WARNING desaparecer y los
#    endpoints protegidos ahora rechazan requests sin Authorization header.
```

### Uso desde curl

```bash
# Sin auth (rechazado 401):
curl -X POST http://127.0.0.1:8000/preview \
  -H "Content-Type: application/json" \
  -d '{"IP_MIKROTIK":"192.168.88.1","DATE":"2025-06-01"}'

# Con auth (OK):
curl -X POST http://127.0.0.1:8000/preview \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer la_key_que_te_dio_el_paso_1" \
  -d '{"IP_MIKROTIK":"192.168.88.1","DATE":"2025-06-01"}'
```

### Qué endpoints se protegen

| Endpoint | Auth |
|---|---|
| `/health` | Pública (para health checks externos) |
| `/preview`, `/script` | Bearer (ejecuta cambios en MikroTik) |
| `/addOptions`, `/readOptions`, `/addDoc` | Bearer (lee/modifica DB) |

### Frontend web

El frontend estático (`/`) **no está integrado con la auth** — está pensado para uso en dev sin auth. Si activás `API_KEY`, vas a ver un error 401 amigable en la UI explicando cómo autenticarte desde curl o un cliente HTTP. Si necesitás un frontend protegido, abrí un issue.

### Comparación timing-safe

La comparación del token usa `secrets.compare_digest()` (no `==`) para evitar timing attacks que podrían filtrar el token byte a byte.

## Setup paso a paso

### 1. MikroTik

Necesitás un router MikroTik con la API habilitada (puerto 8728 por default) y un usuario con permisos para manipular `/ip/firewall/address-list`.

### 2. Archivo `.env`

```ini
# MikroTik
USER_MIKROTIK=admin
PASS_MIKROTIK=tu_password

# Data (rutas, todas relativas al directorio del proyecto)
CSV_PATH=./data/clientes.csv
OPTIONS_DB_PATH=./data/options.db
DATA_DIR=./data

# Opcionales
HOST=127.0.0.1
PORT=8000
```

### 3. Datos de clientes

El CSV debe tener una fila de encabezado con las columnas **`ip`** y **`nombre`**, una fila por cliente:

```csv
ip,nombre
192.168.88.10,Cliente A
192.168.88.11,Cliente B
192.168.88.12,Cliente C
```

El archivo se crea automáticamente al primer arranque a partir de `data/clientes.csv.example`. Editá `data/clientes.csv` con tu lista real.

### 4. Probarlo

```bash
pip install -r requirements.txt
uvicorn main:api --reload
curl http://127.0.0.1:8000/health
```

---

## Docker (recomendado para dueños de WISP)

Si querés un setup "install-and-forget", la forma más simple es Docker Compose. Asume Docker Desktop (Windows/Mac) o Docker Engine (Linux) instalado.

### Setup con docker compose

```bash
# 1. Configurá tus credenciales
cp .env.example .env
# Editá .env: USER_MIKROTIK, PASS_MIKROTIK y (opcional) API_KEY

# 2. Build + arrancar en background
docker compose up -d

# 3. Verificar
docker compose ps
curl http://127.0.0.1:8000/health

# 4. Abrir el panel web
# http://127.0.0.1:8000
```

Los datos (CSV de clientes y DB de opciones) persisten en un **named volume** (`mikrotik_data`) — sobreviven reinicios del container.

### Comandos útiles

```bash
docker compose logs -f          # seguir logs
docker compose restart          # reiniciar
docker compose pull && docker compose up -d --build   # actualizar tras un pull
docker compose down             # parar (datos persisten)
docker compose down -v          # parar y BORRAR datos (¡cuidado!)
```

### Sin docker compose (técnicos)

```bash
docker build -t mikrotik-suspender .

docker run -d \
  --name mikrotik-suspender \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  -v mikrotik_data:/app/data \
  mikrotik-suspender

docker logs -f mikrotik-suspender
```

### Notas sobre Docker

- El container escucha en `0.0.0.0:8000` (ignora el `HOST=127.0.0.1` del `.env.example`, que es para uso sin Docker).
- El healthcheck interno contra `/health` hace que `docker compose ps` muestre el estado real.
- Si activás `API_KEY` en el `.env`, el panel web va a mostrar errores 401 (esperado — la UI es dev-only). Usá curl con `Authorization: Bearer <key>` o abrí un issue si querés una UI protegida.

---

## Bootstrap (auto-arranque)

Al iniciar, la app ejecuta `bootstrap.run()` (idempotente):

1. Crea `data/` si no existe.
2. Copia `data/clientes.csv.example` → `data/clientes.csv` si la runtime CSV falta.
3. Inicializa `data/options.db` (SQLite) con la versión de schema actual.
4. Siembra `DEFAULT_OPTIONS` en la DB si está vacía.

Para empezar de cero, borrá `data/` y reiniciá.

---

## Arquitectura (Clean Architecture)

```
mikrotik-suspender/
├── main.py                ★ Entry point — crea la app FastAPI + lifespan
├── bootstrap.py           ★ Setup idempotente al arranque
│
├── core/                  ▲ CAPA MÁS INTERNA
│   ├── models.py          │  Datos de negocio (SheetEntry, AddressListEntry)
│   ├── interfaces.py      │  Contratos abstractos (puertos)
│   └── config.py          │  Config unificada desde .env
│
├── use_cases/             ◆ LÓGICA DE NEGOCIO
│   ├── suspension.py      │  Preview + Execute
│   └── options_mgmt.py    │  CRUD de opciones
│
├── adapters/              ▢ IMPLEMENTACIONES DE INFRAESTRUCTURA
│   ├── csv_sheet_reader.py│  Lee clientes del CSV (con mtime cache)
│   ├── mikrotik_adapter.py│ RouterOS
│   └── sqlite_options_repo.py │ Persiste opciones en SQLite
│
├── api/                   ▣ TRANSPORTE (FastAPI)
│   ├── router.py          │  Endpoints — solo delegan
│   ├── schemas.py         │  Validación de requests
│   └── dependencies.py    │  Fábricas (Composition Root)
│
├── data/                  ⚙ RUNTIME (gitignored, excepto *.example)
│   ├── clientes.csv.example   ← Plantilla versionada
│   ├── clientes.csv           ← Datos reales (gitignored)
│   └── options.db             ← SQLite (gitignored)
│
└── tests/                 ⚗ TESTS con fakes en memoria
```

### Regla de dependencias

```
api → use_cases → interfaces ← adapters
               → models
```

- `core/` no sabe que existe `api/`, `adapters/` ni `use_cases/`.
- `use_cases/` solo conoce `core/` (interfaces y modelos).
- `adapters/` implementa las interfaces de `core/`.
- `api/` conecta todo usando `dependencies.py`.

Esto permite **cambiar CSV por Excel** o **MikroTik por Cisco** con solo escribir un adapter nuevo — los use cases no se tocan.

---

## Lógica en detalle

### `use_cases/suspension.py` — el corazón de la app

La lógica vive en `SuspensionUseCases` y tiene dos métodos públicos:

```python
async def preview(self, mikrotik_ip, date) -> SuspensionPreview
async def execute(self, mikrotik_ip, date) -> None
```

Ambos comparten dos helpers privados:

**`_sync_new_entries(sheet_entries, mkt_entries)`**
Toma las IPs del CSV y las que ya están en MikroTik. Las que faltan las agrega al address-list `suspendido` con el nombre del cliente como comentario. Devuelve la lista actualizada.

**`_build_comment_map(sheet_entries, mkt_entries, date)`**
Cruza ambas listas: para cada IP que existe tanto en el CSV como en MikroTik, genera dos versiones del comentario:
- La actual (tal como está en MikroTik).
- La final (con `// SUSPENDIDO - {fecha}` concatenado).

La diferencia entre `preview` y `execute`:
- **Preview**: solo cruza datos y devuelve el resultado.
- **Execute**: después de cruzar, llama a `disable_entry()` (activa el bloqueo) y `set_comment()` (actualiza el comentario) para cada entrada.

### ¿Qué significa `disabled=false`?

En RouterOS, el campo `disabled` de un address-list controla si la entrada se aplica:

| Valor | Significado |
|-------|-------------|
| `true` / `yes` | Entrada **inactiva** — el firewall NO la considera |
| `false` / `no` | Entrada **activa** — el firewall la aplica |

El endpoint `/script` setea `disabled=false` para **activar** la suspensión de cada IP.

### `adapters/csv_sheet_reader.py` — caching

El reader mantiene un cache en memoria invalidado por `mtime`. La ruta del CSV se inyecta en construcción (viene de `config.csv_path` por default), así que cada instancia lee siempre del mismo archivo. Si la API recibe varios requests seguidos, el CSV no se re-parsea. Cuando el archivo cambia (mtime nuevo), se invalida y se re-lee.

---

## Tests

```bash
pytest tests/ -v
```

Cubren tres niveles:

| Tipo | Archivo | Qué prueba |
|------|---------|-----------|
| Use cases (con fakes) | `test_suspension.py`, `test_options.py` | Lógica de negocio sin IO real |
| Adapter CSV | `test_csv_sheet_reader.py` | Parseo, cache por mtime, validación de headers |
| Adapter SQLite | `test_sqlite_options_repo.py` | CRUD, idempotencia, schema version |

Los tests de use cases usan **fakes en memoria** (`_FakeSheetReader`, `_FakeMikroTik`, `_FakeOptionsRepo`) que implementan los mismos ports que los adapters reales — la lógica se prueba sin conexión a internet ni credenciales.

---

## Mantenimiento

### Si agregás un nuevo servicio externo (ej. una API de cobranzas)

1. Crear el **port** en `core/interfaces.py` (clase abstracta).
2. Crear el **adapter** en `adapters/` que implemente ese port.
3. Agregar el **use case** o extender uno existente.
4. Conectarlo en `api/dependencies.py`.

### Si cambiás la fuente de datos (CSV → algo más)

Solo tocá `adapters/csv_sheet_reader.py` (o creá un nuevo adapter) — el resto del código no se entera.

### Si cambiás la persistencia de opciones (SQLite → algo más)

Solo tocá `adapters/sqlite_options_repo.py` — el resto del código no se entera.

### Para migrar la DB SQLite a una versión nueva de schema

1. Agregá el SQL de migración en una nueva función en `bootstrap.py`.
2. Detectá la versión actual con `SELECT version FROM schema_version`.
3. Aplicá los cambios incrementalmente.
4. Actualizá el número de versión.

---

## Referencia rápida

| Concepto | Dónde está |
|----------|-----------|
| Config y secrets | `core/config.py` ← `.env` |
| Modelos de datos | `core/models.py` |
| Contratos abstractos | `core/interfaces.py` |
| Lectura de clientes | `adapters/csv_sheet_reader.py` |
| MikroTik | `adapters/mikrotik_adapter.py` |
| Persistencia de opciones | `adapters/sqlite_options_repo.py` |
| Bootstrap al arranque | `bootstrap.py` |
| Lógica de suspensión | `use_cases/suspension.py` |
| Endpoints HTTP | `api/router.py` |
| Tests | `tests/` |
