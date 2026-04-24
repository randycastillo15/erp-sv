# Base de Conocimiento — DTE El Salvador con ERPNext/Frappe

> Documento vivo que consolida todo el conocimiento técnico acumulado del proyecto.
> Sprints 1–9 completos. Última actualización: 2026-04-24.

---

## Índice

1. [Visión general y contexto](#1-visión-general-y-contexto)
2. [Arquitectura del sistema](#2-arquitectura-del-sistema)
3. [Componentes y puertos](#3-componentes-y-puertos)
4. [DTE Gateway (FastAPI)](#4-dte-gateway-fastapi)
5. [App ERPNext: erpnext_localization_sv](#5-app-erpnext-erpnext_localization_sv)
6. [DocTypes creados](#6-doctypes-creados)
7. [Flujo completo: emitir un DTE](#7-flujo-completo-emitir-un-dte)
8. [Flujo: invalidar un DTE](#8-flujo-invalidar-un-dte)
9. [Flujo: contingencia](#9-flujo-contingencia)
10. [Roles y privilegios DTE](#10-roles-y-privilegios-dte)
11. [Configuración: SV DTE Settings](#11-configuración-sv-dte-settings)
12. [Tipos de documentos DTE soportados](#12-tipos-de-documentos-dte-soportados)
13. [Campos DTE en Sales Invoice](#13-campos-dte-en-sales-invoice)
14. [Campos DTE en Customer y Address](#14-campos-dte-en-customer-y-address)
15. [Catálogos fiscales](#15-catálogos-fiscales)
16. [Secuenciales por ejercicio impositivo](#16-secuenciales-por-ejercicio-impositivo)
17. [Historial de sprints](#17-historial-de-sprints)
18. [Patrones técnicos de Frappe aprendidos](#18-patrones-técnicos-de-frappe-aprendidos)
19. [Errores comunes y cómo resolverlos](#19-errores-comunes-y-cómo-resolverlos)
20. [Cómo ejecutar y desplegar](#20-cómo-ejecutar-y-desplegar)
21. [Tests](#21-tests)
22. [Datos de prueba y credenciales de desarrollo](#22-datos-de-prueba-y-credenciales-de-desarrollo)
23. [Artefactos en este directorio](#23-artefactos-en-este-directorio)

---

## 1. Visión general y contexto

**Objetivo:** Integrar ERPNext (Frappe) con el sistema de Documentos Tributarios Electrónicos (DTE) del Ministerio de Hacienda de El Salvador. Permite emitir, consultar, invalidar y reportar contingencias de facturas electrónicas directamente desde Sales Invoice en ERPNext.

**Tipos de documentos soportados:**

| Código | Nombre | Uso |
|--------|--------|-----|
| 01 | Factura Electrónica (FE) | Ventas a consumidores finales |
| 03 | Comprobante de Crédito Fiscal (CCF) | Ventas a contribuyentes con NIT/NRC |
| 05 | Nota de Crédito (NC) | Ajustes/devoluciones a CCF |
| 06 | Nota de Débito (ND) | Cargos adicionales a CCF |

**Ambiente de pruebas:** `00` — API Test MH: `https://apitest.dtes.mh.gob.sv`  
**Ambiente de producción:** `01` — API Prod MH: `https://api.dtes.mh.gob.sv`

**NIT del emisor (desarrollo):** `06141310001389`  
**NRC del emisor (desarrollo):** `2613894`

---

## 2. Arquitectura del sistema

```
┌─────────────────────────────────────────────────────────────────────────┐
│  NAVEGADOR (Frappe UI)                                                  │
│  Sales Invoice form → botones: Emitir DTE / Consultar / Invalidar      │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ AJAX (frappe.call)
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  ERPNEXT / FRAPPE  (devcontainer puerto 8000)                           │
│  erpnext_localization_sv                                                │
│                                                                         │
│  api/dte.py          → emit_dte(), get_dte_status()                     │
│  api/anulacion.py    → anular_dte()                                     │
│  api/contingencia.py → emit_contingencia()                              │
│  api/sv_payload_builder.py → build_emit_request()                       │
│  overrides/sales_invoice.py → on_submit auto-emit                       │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ HTTP POST JSON (sin secretos)
                               │ host.docker.internal:8100
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  DTE GATEWAY (FastAPI, puerto 8100)                                     │
│                                                                         │
│  POST /v2/dte/emit        → orquesta emisión completa                   │
│  POST /v2/dte/status      → consulta estado en MH                       │
│  POST /v2/dte/anular      → invalida DTE PROCESADO                      │
│  POST /v2/dte/contingencia                                               │
│                                                                         │
│  Internamente:                                                           │
│  1. Valida payload contra schema JSON MH                                │
│  2. Llama SVFE Firmador → obtiene JSON firmado                          │
│  3. Obtiene token MH (cacheable 47h pruebas / 23h prod)                 │
│  4. POST a MH /fesv/recepciondte                                        │
│  5. Persiste resultado en dte_store.db (idempotencia + secuenciales)    │
└──────────────┬──────────────────────────┬───────────────────────────────┘
               │                          │
               ▼                          ▼
┌──────────────────────┐   ┌──────────────────────────────────────────────┐
│  SVFE FIRMADOR       │   │  MINISTERIO DE HACIENDA (MH)                 │
│  (puerto 8113)       │   │                                              │
│  Docker: svfe-api-   │   │  apitest.dtes.mh.gob.sv (amb=00)            │
│  firmador            │   │  api.dtes.mh.gob.sv (amb=01)                │
│                      │   │                                              │
│  POST /firmardocu-   │   │  /seguridad/auth     → token                │
│  mento/             │   │  /fesv/recepciondte  → sello                 │
│  Firma con clave     │   │  /fesv/recepcion/consultadte/ → estado       │
│  privada PKCS12      │   │  /fesv/anulardte    → sello anulación        │
└──────────────────────┘   └──────────────────────────────────────────────┘
```

### Principio de diseño: separación de responsabilidades

- **ERPNext** (Frappe): construye el payload de negocio a partir del Sales Invoice. **Nunca maneja secretos** (password_pri, api_password). Solo conoce NIT, NRC, datos del emisor/receptor.
- **DTE Gateway** (FastAPI): orquesta el flujo técnico DTE. Maneja autenticación MH, firma electrónica, reintentos, idempotencia, secuenciales.
- **SVFE Firmador**: binario oficial de Hacienda. Firma el JSON DTE con la clave privada PKCS12.

---

## 3. Componentes y puertos

| Componente | Puerto | Descripción |
|------------|--------|-------------|
| ERPNext/Frappe | 8000 | UI principal + API |
| DTE Gateway (FastAPI) | 8100 → 8000 interno | Orquestador DTE |
| SVFE Firmador | 8113 | Firmador oficial MH |
| MariaDB | 3306 | Base de datos ERPNext |
| Redis Cache | 6379 | Cache Frappe |
| Redis Queue | 6380 | Queue de workers Frappe |

**Contenedor del firmador:** `svfe-api-firmador`  
**Contenedor del gateway:** `dte-gateway`  
**Contenedor ERPNext:** `erpnext_devcontainer-frappe-1`

### Comandos útiles

```bash
# Levantar gateway (desde raíz del repo)
make up

# bench migrate
docker exec -w /workspace/development/frappe-bench erpnext_devcontainer-frappe-1 \
  bench --site development.localhost migrate

# bench build (solo app localización)
docker exec -w /workspace/development/frappe-bench erpnext_devcontainer-frappe-1 \
  bench build --app erpnext_localization_sv

# Ejecutar función Python en Frappe
docker exec -w /workspace/development/frappe-bench erpnext_devcontainer-frappe-1 \
  bench --site development.localhost execute \
  "erpnext_localization_sv.api.dte.ping_gateway"

# Tests del gateway
make test
# o:
docker compose -f infra/compose/docker-compose.yml exec dte-gateway pytest -q
```

---

## 4. DTE Gateway (FastAPI)

**Ruta:** `apps/dte-gateway/`  
**Versión:** 0.6.0  
**Framework:** FastAPI + Pydantic v2

### Estructura interna

```
app/
├── main.py              # FastAPI app, routers montados
├── config.py            # Constantes: MH_ENDPOINT_*, RETRIES, TOKEN_TTL
├── models/
│   ├── dte_request.py   # DTEEmitRequest, DTEStatusRequest, AnulacionRequest
│   └── dte_response.py  # DTEEmitResponse
├── routers/
│   ├── dte.py           # POST /v2/dte/emit, POST /v2/dte/status
│   ├── anulacion.py     # POST /v2/dte/anular
│   └── contingencia.py  # POST /v2/dte/contingencia
├── services/
│   ├── dte_service.py          # Orquestador principal
│   ├── auth_client.py          # Token MH con caché (47h test, 23h prod)
│   ├── signer_client.py        # Llamadas al firmador SVFE
│   ├── mh_client.py            # Comunicación MH (3 reintentos automáticos)
│   ├── control_number.py       # UUID generación + número de control DTE
│   ├── dte_store.py            # Idempotencia + secuenciales SQLite
│   ├── schema_validator.py     # Validación contra schemas JSON oficiales
│   ├── secret_resolver.py      # Lee secretos de variables de entorno
│   └── mappers/
│       ├── common.py           # Funciones compartidas
│       ├── fe_mapper.py        # Factura Electrónica (01)
│       ├── ccf_mapper.py       # Comprobante Crédito Fiscal (03)
│       ├── nc_mapper.py        # Nota de Crédito (05)
│       ├── nd_mapper.py        # Nota de Débito (06)
│       ├── anulacion_mapper.py # Anulación/invalidación
│       └── contingencia_mapper.py
├── schemas/             # JSON schemas oficiales MH
│   ├── fe-fc-v1.json
│   ├── fe-ccf-v3.json
│   ├── fe-nc-v3.json
│   ├── fe-nd-v3.json
│   ├── contingencia-schema-v3.json
│   └── anulacion-schema-v2.json
└── catalogs/
    └── cat_data.py      # CAT-001 a CAT-022
```

### Flujo interno de `POST /v2/dte/emit`

1. Recibe `DTEEmitRequest` (payload sin secretos)
2. Verifica idempotencia en `dte_store.db` → si ya existe, retorna resultado previo
3. Selecciona mapper según `tipo_dte` (01→fe, 03→ccf, 05→nc, 06→nd)
4. Construye JSON DTE con schema MH
5. Valida contra schema JSON oficial
6. Llama `signer_client.py` → POST al firmador → obtiene JSON firmado
7. Obtiene/refresca token MH vía `auth_client.py`
8. POST a `/fesv/recepciondte` con reintentos (mh_client.py)
9. Parsea respuesta: `estado`, `sello_recibido`, `observaciones`, etc.
10. Persiste en `dte_store.db` (secuencial + resultado)
11. Retorna `DTEEmitResponse`

### Respuesta exitosa del gateway

```json
{
  "generation_code": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "control_number":  "DTE-01-M001P001-000000000000001",
  "estado":          "PROCESADO",
  "sello_recibido":  "SELLO40CHARS",
  "fh_procesamiento": "DD/MM/YYYY HH:MM:SS",
  "observaciones":   []
}
```

### Secuenciales (dte_store.db)

La clave de secuencia es la tupla: `(tipo_dte, cod_estable_mh, cod_punto_venta_mh, ambiente, ejercicio)`

- `ejercicio` = año del `posting_date` del documento
- Reinicio automático el 1 de enero (nuevo ejercicio → secuencial = 1)
- `ambiente=00` y `ambiente=01` son completamente independientes
- El formato del número de control es: `DTE-{tipo}-{estable}{pventa}-{secuencial:015d}`

### Idempotencia

Si se envía el mismo `idempotency_key`, el gateway retorna el resultado ya almacenado en `dte_store.db` sin llamar a MH. El key lo construye ERPNext:

```python
f"{frappe.local.site}:Sales Invoice:{doc.name}:{tipo_dte}:{ambiente}"
```

### Variables de entorno del gateway

```bash
# Configuración del firmador
FIRMADOR_URL=http://svfe-api-firmador:8113/firmardocumento/
FIRMADOR_NIT=06141310001389

# Credenciales MH
MH_API_USER=06141310001389
MH_API_PASSWORD=<contraseña_mh>

# Ambientes
DTE_AMBIENTE=00   # 00=pruebas, 01=producción
```

---

## 5. App ERPNext: erpnext_localization_sv

**Ruta:** `infra/erpnext/development/frappe-bench/apps/erpnext_localization_sv/`  
**Frappe version:** v15/v16

### Estructura

```
erpnext_localization_sv/
├── api/
│   ├── dte.py                 # emit_dte(), get_dte_status(), ping_gateway()
│   ├── anulacion.py           # anular_dte()
│   ├── contingencia.py        # emit_contingencia()
│   ├── sv_dte_document.py     # refresh_dte_status()
│   ├── sv_payload_builder.py  # build_emit_request()
│   ├── dte_document_sync.py   # sync_on_emit(), sync_on_status_check(), sync_on_invalidation()
│   └── health.py
├── config/
│   ├── sv_fiscal_constants.py  # URLs MH, regex NIT/NRC, IVA_RATE=0.13
│   └── sv_catalogs.py          # Selectores Frappe para catálogos
├── custom_fields/
│   └── user.py                 # Campos sv_tipo_doc_responsable + sv_num_doc_responsable en User
├── overrides/
│   ├── sales_invoice.py        # on_submit hook — auto-emit DTE
│   ├── customer.py
│   └── address.py
├── public/js/
│   ├── sales_invoice.js        # Botones DTE en Sales Invoice
│   ├── sv_dte_document.js      # Botones en SV DTE Document form
│   ├── sv_dte_settings.js
│   ├── sv_dte_establishment.js
│   ├── sv_dte_document_list.js
│   ├── customer_dte.js
│   └── address_dte.js
├── erpnext_localization_sv/
│   └── doctype/                # 9 DocTypes
├── fixtures/                   # 5 catálogos (JSON)
├── patches/                    # v1_0 a v1_31 (31 versiones)
├── patches.txt                 # Lista completa de patches
└── hooks.py                    # Configuración app
```

### hooks.py — configuración crítica

```python
# Auto-emit on_submit
doc_events = {
    "Sales Invoice": {
        "on_submit": "erpnext_localization_sv.overrides.sales_invoice.on_submit",
    },
}

# JS por DocType
doctype_js = {
    "Sales Invoice":        "public/js/sales_invoice.js",
    "SV DTE Document":      "public/js/sv_dte_document.js",
    # ... 5 más
}

# Fixtures (se cargan en bench migrate)
fixtures = [
    {"dt": "SV Actividad Economica"},
    {"dt": "SV Departamento"},
    {"dt": "SV Municipio"},
    {"dt": "SV Distrito"},
    {"dt": "SV Tipo Documento"},
]
```

### sv_payload_builder.py — función central

`build_emit_request(doc, tipo_dte)` construye el dict para el gateway:

```python
payload = {
    "tipo_dte":       tipo_dte,     # "01", "03", "05", "06"
    "ambiente":       "00" o "01",
    "docname":        doc.name,
    "posting_date":   "YYYY-MM-DD",
    "receptor":       _build_receptor(doc, tipo_dte),
    "items":          _build_items(doc),
    "grand_total":    float,
    "total_iva":      float,
    "emisor":         _build_emisor_settings(settings, estab),
    "idempotency_key": "site:doctype:name:tipo:amb",
    # Para NC (05): agrega documento_relacionado (gen_code del CCF)
    # Para ND (06): agrega documento_relacionado_nd
}
# SIN: password_pri, api_password, firmaElectronica
```

**Cadena de resolución de dirección del receptor:**
1. `doc.customer_address` (selección explícita en el documento)
2. Dirección de facturación default del Customer
3. Fallback: campos `sv_direccion_*` legacy del Customer

**Resolución de municipio:**
- El campo `sv_municipio` es un Link a `SV Municipio` cuyo `name` es `"dept-codigo"` (ej. `"05-25"`)
- `_resolve_municipio()` lee el campo `codigo` del registro para obtener solo `"25"`
- El gateway solo necesita el código relativo (sin el prefijo del departamento)

### api/dte.py — endpoints principales

```python
@frappe.whitelist()
def emit_dte(doctype: str, docname: str) -> dict:
    # Guard: DTE Operador o superior
    # Construye payload via build_emit_request()
    # POST a /v2/dte/emit
    # Persiste en Sales Invoice: generation_code, control_number, estado, sello, qr_url
    # Sincroniza SV DTE Document via sync_on_emit()
    # Crea SV DTE Log (sanitizado)
    # Si estado != PROCESADO: frappe.throw()
    # Retorna resultado sanitizado

@frappe.whitelist()
def get_dte_status(docname: str) -> dict:
    # Guard: cualquier rol DTE
    # POST a /v2/dte/status
    # Actualiza sv_estado_mh en Sales Invoice
    # Sincroniza SV DTE Document via sync_on_status_check()

@frappe.whitelist()
def ping_gateway() -> dict:
    # Guard: DTE Operador o superior
    # GET /health
```

### Sanitización de secretos

Los campos sensibles (`password_pri`, `api_password`, `firmaElectronica`, `token`, etc.) se redactan como `"***REDACTED***"` antes de persisitir en `sv_dte_last_payload` y en `SV DTE Log`. El set `_LOG_SENSITIVE_KEYS` define qué redactar.

---

## 6. DocTypes creados

### SV DTE Settings (singleton)

Configuración global del módulo DTE. Campos principales:

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `ambiente` | Select | `00`=Pruebas, `01`=Producción |
| `nit_emisor` | Data | NIT del emisor (14 dígitos sin guiones) |
| `nrc_emisor` | Data | NRC del emisor |
| `nombre_emisor` | Data | Nombre legal del emisor |
| `nombre_comercial` | Data | Nombre comercial (opcional) |
| `cod_actividad` | Link→SV Actividad Economica | Código actividad MH |
| `desc_actividad` | Data (read-only) | Auto-rellena al seleccionar actividad |
| `establecimiento_default` | Link→SV DTE Establishment | Establecimiento activo |
| `url_firmador` | Data | URL firmador (defecto: `http://host.docker.internal:8113/...`) |
| `emitir_fe` / `emitir_ccf` / `emitir_nc` | Check | Habilitar tipos |
| `emitir_al_someter` | Check | Auto-emit en on_submit (solo FE y CCF) |
| `url_verificacion_mh` | Data | Portal público MH (solo para referencia) |

> **NOTA:** La sección "Responsable" fue eliminada en Sprint 9. Los datos del responsable ahora viven en el perfil del usuario Frappe (`sv_tipo_doc_responsable` + `sv_num_doc_responsable`).

### SV DTE Document (read-only, autoname: DTEDOC-.YYYY.-.#####)

Registro auditable de cada DTE emitido. Se crea/actualiza automáticamente desde `dte_document_sync.py`.

| Campo | Descripción |
|-------|-------------|
| `generation_code` | UUID del DTE (clave de búsqueda) |
| `control_number` | Número de control MH (DTE-01-M001P001-000000000000001) |
| `mh_status` | PENDIENTE / PROCESADO / RECHAZADO / INVALIDADO / CONTINGENCIA |
| `reception_seal` | Sello de recepción MH (40 chars A-Z0-9) |
| `source_doctype` + `source_docname` | Link dinámico al documento origen (Sales Invoice) |
| `mh_request_json` | Payload enviado a MH (sanitizado) |
| `mh_response_json` | Respuesta de MH (sanitizada) |
| `mh_verification_url` | URL parametrizada para verificación pública |
| `is_invalidated` | Si fue invalidado |
| `invalidated_at` | Fecha de invalidación |
| `tipo_anulacion` | 1=Error/reemplazar, 2=Sin reemplazo, 3=Devolución |

### SV DTE Log (autoname: DTELOG-.YYYY.-.#####)

Log inmutable de operaciones DTE. Un registro por operación (emision, consulta, invalidacion, contingencia).

| Campo | Descripción |
|-------|-------------|
| `tipo_evento` | emision / consulta / lote / contingencia / invalidacion |
| `sales_invoice` | Link al Sales Invoice |
| `codigo_generacion` | UUID del DTE |
| `estado_resultante` | Estado retornado por MH |
| `request_json` | Payload enviado (sanitizado) |
| `response_json` | Respuesta recibida (sanitizada) |

### SV DTE Establishment

Datos del establecimiento emisor (pueden existir múltiples).

| Campo | Descripción |
|-------|-------------|
| `cod_estable_mh` | Código asignado por MH (ej. `M001`) |
| `cod_punto_venta_mh` | Código PV asignado por MH (ej. `P001`) |
| `tipo_establecimiento` | `02`=establecimiento, `20`=casa matriz |
| `departamento` | Código departamento (ej. `05`=La Libertad) |
| `municipio` | Link a SV Municipio |
| `complemento` | Dirección complementaria |
| `telefono` | Teléfono del establecimiento |

### SV Tipo Documento (CAT-22, autoname: by field codigo)

Tipos de documento de identidad para el responsable DTE.

| Código | Descripción |
|--------|-------------|
| 36 | NIT |
| 13 | DUI |
| 02 | Carnet de Residente |
| 03 | Pasaporte |
| 37 | Otro |

### SV Actividad Economica (CAT-019)

Giros económicos MH. `autoname: "field:codigo"`. Más de 100 registros cargados como fixture.

### SV Departamento, SV Municipio, SV Distrito

Geografía administrativa de El Salvador. Cargados como fixture.

- Departamento: 14 registros (código 01–14)
- Municipio: ~262 registros (clave: `{dept}-{codigo}`, ej. `"05-25"`)
- El campo `codigo` del municipio es relativo al departamento

---

## 7. Flujo completo: emitir un DTE

### Prerrequisitos

1. **Sales Invoice** en estado `docstatus=1` (submitted)
2. Campo `sv_dte_document_type` seleccionado (FE, CCF, NC, o ND)
3. Para CCF/NC/ND: Customer con `sv_nit`, `sv_nrc`, `sv_cod_actividad` + dirección con departamento/municipio
4. `SV DTE Settings` configurado: NIT emisor, ambiente, establecimiento default, URL firmador
5. DTE Gateway y SVFE Firmador corriendo
6. Usuario con rol `DTE Operador` o superior

### Paso a paso

```
Usuario hace clic en "Emitir DTE"
  │
  ▼ AJAX (frappe.call)
  api/dte.py :: emit_dte(doctype="Sales Invoice", docname="SINV-XXXX")
  │
  ├─ Verifica rol DTE (frozenset intersection)
  ├─ Verifica que no esté ya PROCESADO
  ├─ Determina tipo_dte (etiqueta → código: "FE"→"01", "CCF"→"03", etc.)
  ├─ Llama build_emit_request(doc, tipo_dte) → payload dict (sin secretos)
  │
  ▼ HTTP POST json=payload
  DTE Gateway /v2/dte/emit
  │
  ├─ Verifica idempotency_key (dte_store.db) → ¿ya procesado?
  ├─ Selecciona mapper (fe_mapper / ccf_mapper / nc_mapper / nd_mapper)
  ├─ Construye JSON DTE con todos los campos MH
  ├─ Valida contra schema JSON oficial (fe-fc-v1.json, etc.)
  ├─ Firma: signer_client → POST firmador:8113/firmardocumento/ → JSON firmado
  ├─ Auth: auth_client → POST MH /seguridad/auth → token (cacheable 47h)
  ├─ Transmite: mh_client → POST MH /fesv/recepciondte (3 reintentos)
  ├─ Parsea respuesta MH → estado, sello, numero_control, observaciones
  ├─ Persiste en dte_store.db (secuencial + resultado)
  │
  ▼ Retorna DTEEmitResponse
  api/dte.py
  │
  ├─ frappe.db.set_value("Sales Invoice", docname, {
  │    "sv_dte_generation_code": gen_code,
  │    "sv_dte_control_number": control_number,
  │    "sv_estado_mh": "PROCESADO",
  │    "sv_sello_recepcion": sello,
  │    "sv_dte_qr_url": URL_parametrizada,
  │    "sv_total_iva": total_iva,
  │    ...
  │  })
  ├─ sync_on_emit() → crea/actualiza SV DTE Document
  ├─ _write_dte_log() → crea SV DTE Log (sanitizado)
  ├─ Si estado != PROCESADO: frappe.throw() con observaciones MH
  │
  ▼ Respuesta al cliente JS
  sales_invoice.js :: frm.reload_doc()
  Alerta verde: "DTE emitido"
```

### URL de verificación QR (v1_27+)

```
https://admin.factura.gob.sv/consultaPublica?ambiente={00|01}&codGen={UUID}&fechaEmi={YYYY-MM-DD}
```

Se guarda en `sv_dte_qr_url` del Sales Invoice y en `mh_verification_url` del SV DTE Document. El botón "Ver en Hacienda" usa esta URL directamente.

---

## 8. Flujo: invalidar un DTE

### Requisitos previos

- `sv_estado_mh = "PROCESADO"`
- `sv_sello_recepcion` no vacío (40 chars)
- `sv_dte_control_number` no vacío
- Usuario con rol `DTE Responsable`
- Perfil del usuario con `sv_tipo_doc_responsable` + `sv_num_doc_responsable` completos

### CRÍTICO: orden obligatorio para NC antes de CCF

Si se invalida una CCF que tiene una NC asociada, **la NC debe invalidarse primero**. MH rechaza la anulación del CCF si la NC derivada sigue PROCESADA. Este no es un bug del sistema — es la regla del MH.

### Tipos de anulación

| Tipo | Descripción | Requiere UUID Reemplazo |
|------|-------------|------------------------|
| 1 | Error en el documento — se reemplaza por otro | Sí |
| 2 | Sin reemplazo | No |
| 3 | Devolución de mercancía | Sí (el DTE que reemplaza) |

### Flujo técnico

```
anulacion.py :: anular_dte(docname, tipo_anulacion, motivo_anulacion, ...)
│
├─ Verifica rol "DTE Responsable" en frappe.get_roles()
├─ Verifica estado PROCESADO + gen_code + sello + control_number
├─ Lee datos del responsable del perfil del usuario logueado:
│   user_doc.full_name
│   user_doc.get("sv_tipo_doc_responsable")  → "36" (NIT), "13" (DUI)
│   user_doc.get("sv_num_doc_responsable")   → número sin guiones
├─ Construye payload anulación (con emisor, receptor, responsable, idempotency_key)
│
▼ POST /v2/dte/anular
  → MH /fesv/anulardte → sello_recibido de anulación
│
├─ frappe.db.set_value("Sales Invoice", {
│    "sv_anulacion_status": "Invalidado",
│    "sv_estado_mh": "INVALIDADO",
│  })
├─ sync_on_invalidation() → actualiza SV DTE Document
├─ _write_dte_log() (tipo_evento="invalidacion")
```

---

## 9. Flujo: contingencia

La contingencia se usa cuando el gateway/internet no está disponible y los DTEs se emitieron fuera de línea. Se reporta a MH una vez restaurada la conectividad.

**Solo accesible vía `bench execute` (no hay botón UI):**

```bash
docker exec -w /workspace/development/frappe-bench erpnext_devcontainer-frappe-1 \
  bench --site development.localhost execute \
  "erpnext_localization_sv.api.contingencia.emit_contingencia" \
  --kwargs '{
    "docnames_json": "[\"SINV-0001\", \"SINV-0002\"]",
    "tipo_contingencia": 5,
    "motivo_contingencia": "Falla de conexión a internet",
    "fecha_inicio_contingencia": "2024-01-15T08:00:00",
    "fecha_fin_contingencia": "2024-01-15T10:30:00"
  }'
```

**Tipos de contingencia (CAT-016):**
- `5` = Falla en el servicio de internet
- `1` = Falla en la plataforma del firmador
- Etc. (ver catálogo oficial)

**CRÍTICO:** MH rechaza si la ventana temporal (`f_inicio`/`f_fin`) no coincide exactamente con el horario de la falla declarada.

---

## 10. Roles y privilegios DTE

Cuatro roles **aditivos** a los roles ERPNext. Un usuario necesita su rol ERPNext normal **más** un rol DTE.

```
Accounts User + DTE Operador = puede emitir DTEs
Accounts User + DTE Auditor  = solo puede ver y exportar
```

### Descripción de roles

| Rol | Capacidad |
|-----|-----------|
| **DTE Admin** | Configura SV DTE Settings, establecimientos y catálogos. No invalida DTEs. |
| **DTE Responsable** | Emite, invalida DTEs y reporta contingencias. Requiere datos de identidad en perfil. |
| **DTE Operador** | Emite DTEs y consulta estados MH. No invalida ni contingencias. |
| **DTE Auditor** | Solo lectura + exportación de SV DTE Document y SV DTE Log. |

### Permisos DocType

| DocType | DTE Admin | DTE Responsable | DTE Operador | DTE Auditor |
|---------|-----------|-----------------|--------------|-------------|
| SV DTE Settings | R+W | — | — | — |
| SV DTE Establishment | R+W+C+D | R | R | R |
| SV DTE Document | R | R | R | R+Export |
| SV DTE Log | R | R | R | R+Export |
| SV Tipo Documento | R+W+C+D | R | R | R |
| SV Actividad Economica | R+W+C+D | R | R | R |
| SV Departamento/Municipio/Distrito | R+W+C+D | R | R | R |

### Guards de API (server-side)

```python
_DTE_EMIT_ROLES = frozenset(["DTE Operador", "DTE Responsable", "DTE Admin"])
_DTE_READ_ROLES = frozenset(["DTE Operador", "DTE Responsable", "DTE Admin", "DTE Auditor"])

# Patrón de verificación:
if not (_DTE_EMIT_ROLES & set(frappe.get_roles())):
    frappe.throw("Acceso denegado", title="Acceso denegado")
```

### Botones JS visibles por rol

```javascript
const roles        = frappe.user_roles || [];
const canEmit      = roles.some(r => ["DTE Operador", "DTE Responsable", "DTE Admin"].includes(r));
const canInvalidar = roles.includes("DTE Responsable");
const canRead      = roles.some(r => ["DTE Operador", "DTE Responsable", "DTE Admin", "DTE Auditor"].includes(r));

// Emitir DTE, Re-emitir DTE: solo si canEmit
// Invalidar DTE: solo si canInvalidar
// Consultar Estado, Ver Detalle, Ver en Hacienda: si canRead
```

### Configurar responsable (para invalidaciones)

En el perfil del usuario (Configuración → Usuarios → [usuario]):
- **Tipo Documento Responsable:** Link a SV Tipo Documento (ej. `36` = NIT)
- **Número Documento Responsable:** el número sin guiones (ej. `06141310001389`)

### Patches que crean los roles

- `v1_30.add_dte_responsable_role` — crea DTE Responsable
- `v1_31.add_dte_roles` — crea DTE Admin, DTE Operador, DTE Auditor
- `v1_31.add_dte_role_permissions` — matriz de permisos DocType

**Administrator** recibe automáticamente todos los roles DTE vía los patches.

---

## 11. Configuración: SV DTE Settings

Datos de prueba (ambiente `00`):

| Campo | Valor |
|-------|-------|
| `ambiente` | `00` |
| `nit_emisor` | `06141310001389` |
| `nrc_emisor` | `2613894` (o con guion: `261389-4`) |
| `nombre_emisor` | nombre legal de la empresa |
| `cod_actividad` | (ej. `47190` — Otras ventas al por menor) |
| `establecimiento_default` | nombre del registro SV DTE Establishment |
| `url_firmador` | `http://host.docker.internal:8113/firmardocumento/` |
| `emitir_al_someter` | `0` (manual) o `1` (automático) |

### SV DTE Establishment (datos de prueba)

| Campo | Valor |
|-------|-------|
| `cod_estable_mh` | `M001` |
| `cod_punto_venta_mh` | `P001` |
| `tipo_establecimiento` | `02` |
| `departamento` | `05` |
| `municipio` | `05-25` (Santa Tecla, La Libertad) |
| `complemento` | Dirección completa |

---

## 12. Tipos de documentos DTE soportados

### FE — Factura Electrónica (tipo 01)

- Ventas a **consumidores finales** (sin NIT/NRC)
- El receptor solo necesita nombre
- Schema: `fe-fc-v1.json`
- Emitible desde UI con rol DTE Operador

### CCF — Comprobante de Crédito Fiscal (tipo 03)

- Ventas a **contribuyentes** (con NIT, NRC y actividad económica)
- El Customer debe tener: `sv_nit`, `sv_nrc`, `sv_cod_actividad`
- La Address (billing) debe tener: `sv_departamento`, `sv_municipio`, `address_line1`
- Schema: `fe-ccf-v3.json`
- Emitible desde UI

### NC — Nota de Crédito (tipo 05)

- Ajuste/devolución sobre una **CCF ya PROCESADA**
- Sales Invoice debe ser `Is Return = 1` y `Return Against = {nombre_CCF}`
- El campo `sv_dte_document_type` debe ser `NC`
- El payload incluye `documento_relacionado` con el `generation_code` del CCF original
- Schema: `fe-nc-v3.json`
- **No se auto-emite en on_submit** (requiere acción manual)
- **Para invalidar NC+CCF: invalidar la NC primero**

### ND — Nota de Débito (tipo 06) — validada en homologación (Sprint 6)

- Cargo adicional sobre una **CCF ya PROCESADA**
- Sales Invoice debe ser `Is Return = 1` y `Return Against = {nombre_CCF}`
- El campo `sv_dte_document_type` debe ser `ND`
- **CRÍTICO:** Si el establecimiento está en departamento 05, el municipio del receptor debe ser ≤ 22 (límite del schema ND de MH — no es bug del código)
- Solo CCF como origen (no FE)
- Schema: `fe-nd-v3.json`
- No se auto-emite en on_submit

---

## 13. Campos DTE en Sales Invoice

Todos son custom fields instalados vía patches.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `sv_dte_document_type` | Select | FE / CCF / NC / ND |
| `sv_dte_generation_code` | Data | UUID asignado por gateway |
| `sv_dte_control_number` | Data | Número de control MH |
| `sv_estado_mh` | Select | PROCESADO / RECHAZADO / INVALIDADO / PENDIENTE |
| `sv_sello_recepcion` | Data | Sello 40 chars de MH |
| `sv_fecha_procesamiento` | Datetime | Fecha/hora de procesamiento MH |
| `sv_dte_sent_at` | Datetime | Cuándo se envió el DTE |
| `sv_total_iva` | Currency | IVA calculado (fuente para anulación) |
| `sv_dte_qr_url` | Data | URL parametrizada portal MH |
| `sv_dte_environment` | Data | Ambiente registrado en emisión |
| `sv_observaciones_mh` | Code | JSON con observaciones MH |
| `sv_anulacion_status` | Select | Invalidado / Rechazado |

---

## 14. Campos DTE en Customer y Address

### Customer

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `sv_nit` | Data | NIT del receptor (14 chars, sin guiones en MH) |
| `sv_nrc` | Data | NRC del receptor (sin guiones en payload) |
| `sv_cod_actividad` | Link→SV Actividad Economica | Actividad económica |
| `sv_desc_actividad` | Data (read-only) | Auto-rellena |
| `sv_tipo_persona` | Select | Natural / Jurídica |

### Address (para CCF/NC/ND)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `sv_departamento` | Data | Código departamento (ej. `"05"`) |
| `sv_municipio` | Link→SV Municipio | Link al municipio (name: `"05-25"`) |
| `address_line1` | Data (estándar ERPNext) | Complemento de dirección |

**Cadena de resolución en el payload:**
1. `doc.customer_address` → campos del Address
2. Dirección default del Customer → campos del Address
3. Fallback legacy: `customer.sv_direccion_departamento`, `customer.sv_direccion_municipio`, etc.

---

## 15. Catálogos fiscales

Todos se cargan como fixtures en `bench migrate`.

### SV Actividad Economica (CAT-019)

- `autoname: "field:codigo"` — el nombre del registro ES el código (ej. `"47190"`)
- Link field almacena el código directamente → el gateway recibe el valor correcto sin transformación
- `show_title_field_in_link: 1` con `title_field: "descripcion"` → búsqueda muestra descripción

### SV Departamento (CAT-012)

```
name = codigo = "01" a "14"
Ej: "05" = La Libertad
```

### SV Municipio (CAT-013)

```
name = "{dept}-{codigo}"  →  "05-25" = Santa Tecla (municipio 25 del dept 05)
campos: departamento (Link), codigo ("25"), nombre ("Santa Tecla")
```

La función `_resolve_municipio(value)` convierte el name del Link (`"05-25"`) al código relativo (`"25"`) que espera el gateway.

### SV Tipo Documento (CAT-022) — Sprint 9

```
name = codigo = "36" (NIT), "13" (DUI), "02", "03", "37", etc.
```

### SV Distrito

Catálogo de distritos (anidados a municipios).

---

## 16. Secuenciales por ejercicio impositivo

Implementado en Sprint 8. El secuencial se calcula en el gateway (`dte_store.py`).

**Clave de secuencia:** `(tipo_dte, cod_estable_mh, cod_punto_venta_mh, ambiente, ejercicio)`

- `ejercicio` = año tomado del `posting_date` del Sales Invoice
- El 1 de enero de cada año, el secuencial reinicia automáticamente a 1
- `ambiente=00` (pruebas) y `ambiente=01` (prod) son COMPLETAMENTE INDEPENDIENTES — no interfieren entre sí
- Huecos en la secuencia son permitidos por MH (ej. al re-emitir un rechazado)

**Formato número de control:**
```
DTE-{tipo_dte}-{cod_estable_mh}{cod_punto_venta_mh}-{secuencial:015d}
Ejemplo: DTE-01-M001P001-000000000000001
```

**Backfill:** Al migrar de v1 a v2 del gateway, los secuenciales existentes se asignan conservadoramente al ambiente `00`.

---

## 17. Historial de sprints

### Sprint 1 — Scaffolding inicial

- Setup del proyecto: Frappe app + FastAPI gateway
- DocTypes básicos: SV DTE Settings, SV DTE Establishment
- Estructura de directorios

### Sprint 2 — Emisión real FE con MH

- Primer DTE real emitido al MH de El Salvador (amb=00)
- Configuración real: DUI 9 dígitos, establecimiento M001/P001, dept 05 mun 25
- Gateway v1: `build_emit_request()`, firma con SVFE, auth MH, POST recepciondte
- Campos custom en Sales Invoice (v1_0 a v1_1)
- Lección: NIT del emisor debe ser 14 dígitos sin guiones; NRC sin guiones para el gateway

### Sprint 3 — CCF + NC real con MH

- Soporte CCF (tipo 03) y NC (tipo 05)
- Diferencias de schema NC vs CCF: `documentoRelacionado` obligatorio en NC
- Customer v1.3 fields: `sv_nit`, `sv_nrc`, `sv_cod_actividad`
- Mapeo label→código: `"FE"→"01"`, `"CCF"→"03"`, `"NC"→"05"`
- Patches v1_2, v1_3

### Sprint 4 — Anulación/Invalidación + Contingencia

- `anular_dte()` implementado y validado con MH real
- `emit_contingencia()` implementado (solo vía bench execute)
- Persistencia de `sv_total_iva` en emisión (fuente primaria para `montoIva` en anulación)
- SV DTE Log con `tipo_evento` y `codigo_generacion`
- Patches v1_4, v1_5

### Sprint 5 — UX: botones en Sales Invoice

- `public/js/sales_invoice.js`: Emitir DTE, Consultar Estado MH, Re-emitir DTE, Invalidar DTE
- Guard PROCESADO en `emit_dte()` (no re-emitir si ya procesado)
- Mensajes accionables MH (throw/msgprint según estado)
- Patch v1_6 (add_auto_emit_setting)
- `on_submit` hook: auto-emit configurable

### Sprint 6 — ND (Nota de Débito) + Smoke tests

- Nota de Débito (tipo 06) validada en homologación — MH retornó PROCESADO
- `nd_mapper.py` con schema `fe-nd-v3.json`
- Smoke tests: `tests/smoke/` con resultados "2 PASS | 0 FAIL"
- 97 tests unitarios verdes en el gateway
- CRÍTICO descubierto: municipio del receptor ≤ 22 si dept 05 (restricción schema ND MH)

### Sprint 7 — SV DTE Document + QR parametrizado

- Nuevo DocType `SV DTE Document`: registro auditable central de DTEs
- `dte_document_sync.py`: sync en emisión, consulta e invalidación
- URL QR parametrizada: `?ambiente=XX&codGen=UUID&fechaEmi=YYYY-MM-DD`
- Campo `sv_dte_qr_url` en Sales Invoice
- Print Format "DTE El Salvador"
- Botón "Ver en Hacienda" con URL directa (sin diálogo)
- Patches v1_20 a v1_28

### Sprint 8 — Secuenciales por ejercicio impositivo + Limpieza

- `dte_store.py`: clave de secuencia con año fiscal, rollover automático 1-enero
- Aislamiento total amb=00/amb=01
- Eliminación de 15 campos legacy de Sales Invoice (patch v1_29)
- Gateway v0.5.0

### Sprint 9 — Sistema completo de roles y privilegios

- DocType CAT-22 `SV Tipo Documento` (tipos de doc de identidad)
- Sección "Responsable" eliminada de SV DTE Settings → moved a perfil User
- 4 roles DTE aditivos: DTE Admin, DTE Responsable, DTE Operador, DTE Auditor
- Guards server-side en todos los endpoints DTE
- Visibilidad de botones client-side por rol (`frappe.user_roles`)
- Patches v1_30, v1_31

---

## 18. Patrones técnicos de Frappe aprendidos

### Verificar roles

```python
# CORRECTO — frappe.get_roles() retorna lista de roles del usuario actual
if "DTE Responsable" not in frappe.get_roles():
    frappe.throw("Acceso denegado")

# CORRECTO — verificar cualquiera de múltiples roles
_ROLES = frozenset(["DTE Operador", "DTE Responsable", "DTE Admin"])
if not (_ROLES & set(frappe.get_roles())):
    frappe.throw("Acceso denegado")

# INCORRECTO — frappe.has_role() no existe en esta versión
# frappe.has_role("DTE Operador")  # AttributeError
```

### Leer Single doctypes

```python
# CORRECTO — para campos que existen en el DocType
value = frappe.get_single("SV DTE Settings").get("campo")
value = frappe.db.get_single_value("SV DTE Settings", "campo")

# CORRECTO — cuando el campo fue eliminado del DocType JSON (patches de limpieza)
rows = frappe.db.sql(
    "SELECT `value` FROM `tabSingles` WHERE `doctype`='SV DTE Settings' AND `field`=%s LIMIT 1",
    (field_name,),
)
value = rows[0][0] if rows else ""

# INCORRECTO — tabSingles no tiene columna 'modified', get_value() la agrega
# frappe.db.get_value("Singles", {"doctype": "SV DTE Settings", "field": campo}, "value")
# Falla con: "Unknown column 'modified' in 'order clause'"
```

### Custom fields en User (perfil)

```python
# Instalar vía patches — NO vía DocType JSON (User es estándar ERPNext)
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

create_custom_fields({
    "User": [
        {"fieldname": "sv_tipo_doc_responsable", "fieldtype": "Link", "options": "SV Tipo Documento"},
        {"fieldname": "sv_num_doc_responsable",  "fieldtype": "Data"},
    ]
})
```

### Patches de Frappe

```python
# Cada patch = función execute() en su módulo
def execute():
    import frappe
    # ... lógica
    frappe.db.commit()

# Patrón para mover datos de Single a User
rows = frappe.db.sql("SELECT value FROM tabSingles WHERE doctype=... AND field=... LIMIT 1", (f,))
valor = rows[0][0] if rows else ""
```

### DocTypes con autoname by field

```json
{
  "autoname": "field:codigo",
  "title_field": "descripcion",
  "show_title_field_in_link": 1
}
```

Esto hace que `name = codigo` → el valor almacenado en Link fields ES el código fiscal directamente. No requiere transformación al construir payloads MH.

### frappe.db.set_value vs doc.save()

```python
# RÁPIDO — actualiza sin cargar el doc completo ni disparar hooks
frappe.db.set_value("Sales Invoice", docname, {
    "sv_dte_generation_code": gen_code,
    "sv_estado_mh": "PROCESADO",
})
frappe.db.commit()

# LENTO — carga el doc, dispara validate/save hooks, más overhead
doc.sv_estado_mh = "PROCESADO"
doc.save(ignore_permissions=True)
```

### Column Break y Section Break en Frappe forms

Los `Column Break` en el formulario de Frappe crean layouts de 2 columnas. Problemas comunes:

- Un `Section Break` oculto (`hidden=1`) que contiene un `Column Break` rompe el layout
- Para neutralizar un Column Break existente sin eliminarlo: cambiar `fieldtype` a `Data` y poner `hidden=1`
- Nunca dejar Section Breaks huérfanos en el header del formulario

### Permisos DocType vía patch

```python
import frappe.permissions

# Crear entrada si no existe
if not frappe.db.get_value("DocPerm", {"parent": doctype, "role": role, "permlevel": 0}, "name"):
    frappe.permissions.add_permission(doctype, role, 0)

# Establecer permisos específicos
for ptype in ["read", "write", "create", "delete"]:
    frappe.permissions.update_permission_property(doctype, role, 0, ptype, 1 if ptype in perms else 0)
```

### bench migrate — lock file

Si bench migrate falla y deja un lock file:

```bash
docker exec erpnext_devcontainer-frappe-1 \
  rm -f /workspace/development/frappe-bench/sites/development.localhost/locks/bench_migrate.lock
```

### Controlador Python obligatorio para cada DocType

Cada `doctype.json` NECESITA un archivo `doctype.py` con la clase controller, o `bench migrate` lanza `ImportError`.

```python
# sv_tipo_documento.py — mínimo requerido
from frappe.model.document import Document

class SVTipoDocumento(Document):
    pass
```

### Usuario Administrator en Frappe

Administrator es **superusuario** — tiene acceso implícito a todo sin importar qué roles estén en `tabHas Role`. Los tests de "quitar rol a Administrator y verificar que no puede acceder" no son válidos. Para tests de roles, usar un usuario normal.

---

## 19. Errores comunes y cómo resolverlos

### Error: "El DTE ya fue PROCESADO"

**Causa:** Se intenta emitir un Sales Invoice cuyo `sv_estado_mh = "PROCESADO"`.  
**Solución:** Si fue un error, usar "Invalidar DTE". Si fue un rechazo, usar "Re-emitir DTE".

### Error: "No tiene Código de Generación DTE" en anulación

**Causa:** Se intenta anular un DTE que nunca fue emitido.  
**Solución:** Emitir primero.

### Error: "No tiene Sello de Recepción"

**Causa:** El DTE fue emitido pero MH no retornó sello (estado RECHAZADO).  
**Solución:** Re-emitir y asegurar que quede PROCESADO antes de intentar anular.

### Error MH: código `027` — Fecha/Hora Transmisión

**Causa:** La diferencia entre la fecha/hora del DTE y la hora actual del servidor MH excede el umbral permitido.  
**Solución:** Verificar zona horaria del servidor. El `posting_time` del Sales Invoice debe estar en UTC o con offset correcto.

### Error MH: código `028` — Schema inválido

**Causa:** El JSON DTE no pasa la validación de schema MH.  
**Solución:** Revisar el mapper correspondiente. Frecuente en NC/ND si falta el campo `documentoRelacionado`.

### Error: "municipio del receptor incompatible con schema ND"

**Causa:** El municipio del receptor tiene código > 22 en departamento 05.  
**Solución:** Verificar en SV Municipio. No es bug del código — restricción del schema oficial MH para ND.

### Error: "Unknown column 'modified' in order clause"

**Causa:** Se usó `frappe.db.get_value("Singles", ...)`. La tabla `tabSingles` no tiene columna `modified`.  
**Solución:** Usar SQL directo: `frappe.db.sql("SELECT value FROM tabSingles WHERE doctype=... AND field=...")`.

### Error: `ImportError: No module named '...<doctype>'`

**Causa:** Existe el JSON del DocType pero falta el archivo `.py` controller.  
**Solución:** Crear `<doctype>.py` con `class NombreDocType(Document): pass`.

### Error: bench migrate con lock

**Causa:** Un proceso anterior de migrate terminó abruptamente.  
**Solución:**
```bash
docker exec erpnext_devcontainer-frappe-1 \
  rm -f /workspace/development/frappe-bench/sites/development.localhost/locks/bench_migrate.lock
```

### Error: conexión rechazada al gateway (port 8100)

**Causa:** El contenedor del gateway no está corriendo.  
**Solución:**
```bash
make up
# verificar:
docker ps | grep dte-gateway
curl http://localhost:8100/health
```

### Error: token MH expirado

**Causa:** El token MH (47h test, 23h prod) expiró y el gateway no lo refrescó automáticamente.  
**Solución:** El gateway refresca automáticamente. Si persiste, reiniciar el contenedor gateway para limpiar la caché en memoria.

---

## 20. Cómo ejecutar y desplegar

### Entorno de desarrollo

**Requisitos:**
- Docker Desktop (WSL2 en Windows)
- Devcontainer de ERPNext corriendo
- `apps/dte-gateway/.env` configurado

**Pasos iniciales:**

```bash
# 1. Levantar gateway y firmador
cd /home/e105277/projects/erp-sv
make up

# 2. Verificar que ERPNext está corriendo (devcontainer)
docker ps | grep erpnext

# 3. Aplicar migraciones (si hay cambios)
docker exec -w /workspace/development/frappe-bench erpnext_devcontainer-frappe-1 \
  bench --site development.localhost migrate

# 4. Construir assets JS (si se modificaron archivos .js)
docker exec -w /workspace/development/frappe-bench erpnext_devcontainer-frappe-1 \
  bench build --app erpnext_localization_sv

# 5. Verificar conectividad
curl http://localhost:8100/health
```

### Despliegue a producción

Cambios requeridos vs desarrollo:

1. `SV DTE Settings.ambiente = "01"`
2. Variables de entorno en el gateway apuntando a credenciales PROD
3. Actualizar certificado/clave del firmador con los de producción
4. `bench migrate` en el servidor de producción
5. Verificar `dte_store.db` — respaldar antes de actualizar
6. Primer FE real en producción: verificar en portal MH amb=01

**Checklist completo en `docs/runbook_operativo.md` § 19.**

---

## 21. Tests

### Tests unitarios del gateway

**Ubicación:** `apps/dte-gateway/tests/`  
**Cantidad:** 97 tests verdes  
**Ejecutar:**

```bash
docker compose -f infra/compose/docker-compose.yml exec dte-gateway pytest -q
# o:
make test
```

**Cobertura:**
- `test_dte_service.py` — flujo end-to-end con mocks
- `test_mappers.py` — FE, CCF, NC, ND (casos normales + edge cases)
- `test_dte_store.py` — secuenciales, rollover anual, idempotencia
- `test_auth_client.py` — cache de token, expiración
- `test_schema_validator.py` — validación contra schemas MH
- `test_secret_resolver.py` — resolución de secretos desde env

### Smoke tests

**Ubicación:** `apps/dte-gateway/tests/smoke/`  
**Ejecutar contra MH real (amb=00):**

```bash
# Requiere gateway corriendo y credenciales MH en .env
docker compose -f infra/compose/docker-compose.yml exec dte-gateway \
  pytest tests/smoke/ -v
```

**Resultado esperado:** `2 PASS | 0 FAIL | N SKIP`

### Tests ERPNext (app)

No hay tests unitarios de Python para la app Frappe (solo integración manual). La validación se hace vía smoke tests y pruebas manuales en la UI.

---

## 22. Datos de prueba y credenciales de desarrollo

**IMPORTANTE:** Estas credenciales son SOLO para el ambiente de pruebas (amb=00) del MH. No usar en producción.

| Dato | Valor |
|------|-------|
| NIT emisor | `06141310001389` |
| NRC emisor | `2613894` |
| Departamento establecimiento | `05` (La Libertad) |
| Municipio establecimiento | `25` (Santa Tecla) → `05-25` en SV Municipio |
| Cod. establecimiento MH | `M001` |
| Cod. punto de venta MH | `P001` |
| Ambiente | `00` |
| DUI responsable dev | `061172006` (tipo: DUI=13) |
| Certificado | `dte-knowledge/Certificado_06141310001389.crt` |
| Clave privada | `dte-knowledge/PrivateKey_06141310001389.key` |

**Sales Invoice de prueba:**
- Customer "Consumidor Final" → FE (sin NIT/NRC)
- Customer con NIT + NRC + actividad → CCF
- Customer con CCF previo PROCESADO → NC o ND (Is Return=1, Return Against=CCF)

---

## 23. Artefactos en este directorio

| Archivo | Descripción |
|---------|-------------|
| `Certificado_06141310001389.crt` | Certificado X.509 del emisor (desarrollo) |
| `PrivateKey_06141310001389.key` | Clave privada (PKCS12) — solo para env de pruebas |
| `PublicteKey_06141310001389.key` | Clave pública correspondiente |
| `autorizacion_dte.pdf` | Autorización oficial MH para emitir DTEs |
| `catalogo-de-municipios-y-distritos.xlsx` | Catálogo oficial completo de municipios |
| `Manual de Usuario del Sistema de Facturación.pdf` | Manual operativo MH |
| `informacionFacturador.pdf` | Info del firmador SVFE |
| `Capturas/` | Screenshots del desarrollo y pruebas (12 imágenes) |
| `Informacion tecnica y funcional/` | PDFs técnicos MH, schemas JSON, catálogos, normativa |

**En `Informacion tecnica y funcional/`:**

| Archivo | Uso |
|---------|-----|
| `Manual Técnico para la Integración Tecnológica...pdf` | **Referencia principal** — endpoints, schemas, flujos |
| `Catálogo - Sistema de Transmisión.pdf` | CAT-001 a CAT-022 completos |
| `Catálogos del Sistema de Transmisión V 1.2.xlsx` | Catálogos en Excel (para fixtures) |
| `Normativa de Cumplimiento...pdf` | Normativa fiscal vigente |
| `svfe-json-schemas.zip` | Schemas JSON oficiales MH (fuente de `app/schemas/*.json`) |
| `svfe-api-firmador.zip` | Firmador SVFE — binarios y docs |

---

## Apéndice: Constantes fiscales clave

```python
# IVA
IVA_RATE = Decimal("0.13")  # 13%

# Endpoints MH
MH_ENDPOINT_TEST = "https://apitest.dtes.mh.gob.sv"
MH_ENDPOINT_PROD = "https://api.dtes.mh.gob.sv"
MH_AUTH_PATH     = "/seguridad/auth"
MH_RECEIVE_PATH  = "/fesv/recepciondte"
MH_QUERY_PATH    = "/fesv/recepcion/consultadte/"
MH_ANULAR_PATH   = "/fesv/anulardte"

# Portal QR
MH_QR_URL = "https://admin.factura.gob.sv/consultaPublica?ambiente={ambiente}&codGen={cod_gen}&fechaEmi={fecha_emi}"

# Gateway local
DTE_GATEWAY_URL = "http://host.docker.internal:8100"

# Firmador local
FIRMADOR_URL_DEFAULT = "http://host.docker.internal:8113/firmardocumento/"
```

## Apéndice: Campos de respuesta MH importantes

| Campo respuesta | Descripción | Dónde se persiste |
|-----------------|-------------|-------------------|
| `estado` | PROCESADO / RECHAZADO | `sv_estado_mh` |
| `sello_recibido` | 40 chars A-Z0-9 | `sv_sello_recepcion` |
| `fh_procesamiento` | "DD/MM/YYYY HH:MM:SS" | `sv_fecha_procesamiento` (convertido a MySQL) |
| `observaciones` | Lista de strings | `sv_observaciones_mh` (JSON array) |
| `clasificaMsg` | Categoría del mensaje MH | mostrado en UI |
| `descripcionMsg` | Descripción del mensaje | mostrado en UI |

La función `_parse_mh_datetime()` convierte el formato de fecha MH (`DD/MM/YYYY HH:MM:SS`) al formato MySQL (`YYYY-MM-DD HH:MM:SS`).
