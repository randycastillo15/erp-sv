# Runbook Operativo — DTE El Salvador

> Sistema de facturación electrónica El Salvador integrado con ERPNext y el DTE Gateway.
> Revisado: Sprint 5 — Abril 2026.

---

## 1. Prerrequisitos

| Componente | Puerto | Notas |
|------------|--------|-------|
| ERPNext (Frappe) | 8000 | Site: `development.localhost` |
| DTE Gateway (FastAPI) | 8100 | `dte-gateway` container |
| Firmador SVFE | 8113 | `svfe-api-firmador` container |
| MariaDB | 3306 | `erpnext_devcontainer-mariadb-1` |

**Configuración requerida en SV DTE Settings (ERPNext):**
- `nit_emisor`: NIT real del emisor (9 dígitos DUI-homologado o 14 dígitos NIT)
- `ambiente`: `00` (pruebas) o `01` (producción)
- `sv_nombre_responsable`, `sv_tipo_doc_responsable`, `sv_num_doc_responsable`: datos del responsable autorizado

---

## 2. Levantar entorno

```bash
cd erp-sv
make up           # Levanta todos los contenedores
docker ps         # Verificar que todos estén Up
```

Contenedores esperados:
- `dte-gateway`
- `svfe-api-firmador`
- `erpnext_devcontainer-frappe-1`
- `erpnext_devcontainer-mariadb-1`
- `erpnext_devcontainer-redis-cache-1`
- `erpnext_devcontainer-redis-queue-1`

---

## 3. Verificar conectividad

```bash
# Gateway online
curl http://localhost:8100/health
# Respuesta esperada: {"status": "ok", ...}

# Desde ERPNext (via bench)
docker exec -w /workspace/development/frappe-bench erpnext_devcontainer-frappe-1 \
  bench --site development.localhost execute \
  "erpnext_localization_sv.api.dte.ping_gateway"
```

---

## 4. Emitir FE / CCF / NC desde UI

### Pasos:
1. Abrir Sales Invoice **enviada** (docstatus = 1).
2. Seleccionar `sv_dte_document_type` (FE, CCF o NC) — campo obligatorio.
3. Para CCF/NC: el Customer debe tener `sv_nit` configurado.
4. Hacer clic en **DTE El Salvador → Emitir DTE**.
5. Esperar freeze (hasta 30s — incluye firma + MH).
6. El formulario se recarga con:
   - `sv_dte_generation_code`: UUID del DTE
   - `sv_dte_control_number`: DTE-01-XXXXX
   - `sv_estado_mh`: PROCESADO (si MH aceptó) o RECHAZADO

### Estados esperados:
- **PROCESADO**: DTE aceptado por MH. El sello de recepción queda en `sv_sello_recepcion`.
- **RECHAZADO**: MH rechazó el DTE. El formulario muestra el motivo. Usar "Re-emitir DTE" tras corregir datos.

### CCF — campos requeridos en Customer:
- `sv_nit`: NIT del receptor (9 dígitos sin guiones para DUI homologado, o 14 para NIT)
- `sv_nrc`: NRC del receptor

---

## 5. Consultar estado DTE

1. Abrir Sales Invoice con DTE emitido.
2. **DTE El Salvador → Consultar Estado MH**.
3. El campo `sv_estado_mh` se actualiza desde MH.

**Vía bench (admin):**
```bash
docker exec -w /workspace/development/frappe-bench erpnext_devcontainer-frappe-1 \
  bench --site development.localhost execute \
  "erpnext_localization_sv.api.dte.get_dte_status" \
  --kwargs '{"docname": "ACC-SINV-2026-00001"}'
```

---

## 6. Anular DTE (Invalidación)

### Requisitos:
- `sv_estado_mh` = **PROCESADO**
- `sv_sello_recepcion` presente
- `sv_dte_control_number` presente

### Desde UI:
1. Abrir Sales Invoice PROCESADA.
2. **DTE El Salvador → Anular DTE** (botón rojo).
3. Completar el diálogo:
   - **Tipo**: 1 (Error/reemplazar), 2 (Sin reemplazo), 3 (Devolución)
   - **Motivo**: descripción libre
   - **UUID Reemplazo**: solo para tipos 1 y 3
4. Confirmar. El formulario mostrará `sv_estado_mh = INVALIDADO`.

### Orden obligatorio para NC + CCF relacionados:
> **Siempre anular la NC antes del CCF.** MH retorna error 028 si se intenta anular un CCF que tiene una NC vinculada no anulada.

### Vía bench (admin):
```bash
docker exec -w /workspace/development/frappe-bench erpnext_devcontainer-frappe-1 \
  bench --site development.localhost execute \
  "erpnext_localization_sv.api.anulacion.anular_dte" \
  --kwargs '{
    "docname": "ACC-SINV-2026-00001",
    "tipo_anulacion": 2,
    "motivo_anulacion": "Error en datos"
  }'
```

---

## 7. Reportar contingencia (admin only)

La contingencia se opera exclusivamente via `bench execute` — no hay botón en UI porque el ciclo offline no está completamente validado.

```bash
docker exec -w /workspace/development/frappe-bench erpnext_devcontainer-frappe-1 \
  bench --site development.localhost execute \
  "erpnext_localization_sv.api.contingencia.emit_contingencia" \
  --kwargs '{
    "docnames_json": "[\"ACC-SINV-2026-00001\", \"ACC-SINV-2026-00002\"]",
    "tipo_contingencia": 5,
    "motivo_contingencia": "Falla de conexión a internet",
    "f_inicio": "2026-04-05",
    "h_inicio": "10:00:00",
    "f_fin": "2026-04-05",
    "h_fin": "12:00:00"
  }'
```

**Nota:** MH rechaza contingencias si la ventana de tiempo `f_inicio/f_fin` no corresponde al período real de contingencia. El rechazo "FECHA/HORA TRANSMISION FUERA DE PLAZO PERMITIDO" indica schema válido — ajustar las fechas al período correcto.

---

## 8. Interpretar errores MH comunes

| Código / Mensaje | Significado | Acción |
|-----------------|-------------|--------|
| **027** | `numDocumento` del receptor no coincide con el DTE original | Verificar `sv_nit` en Customer; debe coincidir exactamente con lo enviado en el DTE |
| **028** | DTE relacionado con otro DTE activo | Para CCF con NC vinculada: anular NC primero, luego CCF |
| **FECHA/HORA TRANSMISION FUERA DE PLAZO PERMITIDO** | Contingencia fuera de la ventana temporal | Ajustar `f_inicio`/`f_fin` al período real de contingencia |
| **RECHAZADO** (sin código específico) | MH rechazó el DTE | Revisar `sv_observaciones_mh` en Sales Invoice y el log en SV DTE Log |
| HTTP 422 del gateway | Payload inválido contra schema MH | Revisar campos requeridos del tipo DTE |
| HTTP 502 del gateway | MH no respondió tras 3 reintentos | Revisar conectividad, reintentar manualmente |

---

## 9. SV DTE Log

Cada operación (emisión, invalidación, contingencia) crea una entrada en **SV DTE Log**.

### Campos clave:
| Campo | Descripción |
|-------|-------------|
| `tipo_evento` | `emision`, `invalidacion`, `contingencia` |
| `estado_resultante` | Estado retornado por MH (PROCESADO, RECHAZADO, INVALIDADO) |
| `codigo_generacion` | UUID del DTE o evento |
| `request_json` | Payload enviado al gateway (sensibles redactados con `***REDACTED***`) |
| `response_json` | Respuesta del gateway (sanitizada) |

### Acceso:
1. ERPNext → Buscar "SV DTE Log"
2. Filtrar por `sales_invoice` o `tipo_evento`
3. Para diagnóstico: revisar `response_json` → campo `observaciones` del MH

---

## 10. Smoke tests

Verificación rápida de conectividad y flujo mínimo:

```bash
# Solo health + FE (obligatorios, sin env vars)
bash apps/dte-gateway/tests/smoke/run_all_smoke.sh

# Con consulta de estado
GEN_CODE=<uuid> TIPO_DTE=01 \
bash apps/dte-gateway/tests/smoke/run_all_smoke.sh

# Flujo completo
GEN_CODE=<uuid> SELLO=<sello> NUM_CONTROL=DTE-01-... FEC_EMI=2026-04-05 TIPO_DTE=01 \
GEN_CODE_1=<uuid1> GEN_CODE_2=<uuid2> \
bash apps/dte-gateway/tests/smoke/run_all_smoke.sh
```

Salida exitosa: `2 PASS | 0 FAIL | N SKIP`

---

## 11. Unit tests del gateway

```bash
cd apps/dte-gateway
docker exec -w /workspace/dte-gateway dte-gateway pytest -q 2>&1 | tail -5
# Esperado: XX passed, 0 failed
```

Actualmente: **84+ tests** verdes.
