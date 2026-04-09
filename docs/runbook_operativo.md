# Runbook Operativo — DTE El Salvador

> Sistema de facturación electrónica El Salvador integrado con ERPNext y el DTE Gateway.
> Revisado: Sprint 7 — Abril 2026 (consolidación: Print Format receptor fiscal, checklists operativos, smoke CCF/NC/ND PROCESADO).

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
2. Seleccionar `sv_dte_document_type` (FE, CCF, NC o ND) — campo obligatorio.
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

## 6. Invalidar DTE

### Requisitos:
- `sv_estado_mh` = **PROCESADO**
- `sv_sello_recepcion` presente
- `sv_dte_control_number` presente

### Desde UI:
1. Abrir Sales Invoice PROCESADA.
2. **DTE El Salvador → Invalidar DTE** (botón rojo).
3. Completar el diálogo:
   - **Tipo Invalidación**: 1 (Error/reemplazar), 2 (Sin reemplazo), 3 (Devolución)
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

Actualmente: **90 tests** verdes (incluye 6 tests de nd_mapper).

---

## 12. Smoke tests individuales CCF / NC / ND

Los smoke tests de CCF, NC y ND requieren datos reales registrados en MH. Los valores por defecto (`common.sh`) corresponden al NIT/NRC del emisor del entorno de desarrollo.

```bash
# CCF (standalone)
bash apps/dte-gateway/tests/smoke/smoke_ccf.sh
# Exporta: GEN_CODE_CCF=<uuid>

# NC (requiere CCF_GEN_CODE del paso anterior)
CCF_GEN_CODE=<uuid-del-ccf> bash apps/dte-gateway/tests/smoke/smoke_nc.sh

# ND (requiere un CCF nuevo — no usar el mismo CCF que ya tiene una NC)
bash apps/dte-gateway/tests/smoke/smoke_ccf.sh   # nuevo CCF
CCF_GEN_CODE=<uuid-nuevo-ccf> bash apps/dte-gateway/tests/smoke/smoke_nd.sh
```

> **Nota**: El NRC del receptor por defecto (`CCF_RECEPTOR_NRC=3074618`) corresponde al Customer "Grant Plastics Ltd." en el entorno de desarrollo. Para cambiar el receptor en otro entorno, pasar `CCF_RECEPTOR_NIT` y `CCF_RECEPTOR_NRC` como env vars.

---

## 13. Nota de Débito (ND — tipo 06)

### Estado de validación (Sprint 6)
ND fue validada técnicamente en ambiente de homologación: schema local OK, firmador OK, **MH retornó PROCESADO** con sello real. El código (F-1 receptor completo, F-2 `numPagoElectronico`) está funcional. El riesgo residual es exclusivamente de datos maestros (ver checklist abajo).

### Prerrequisitos:
- Existe un CCF **PROCESADO** como documento origen.
- El Customer tiene `sv_nit`, `sv_nrc`, `sv_cod_actividad`, `sv_direccion_*` y `sv_correo` configurados.
- El Sales Invoice ND debe tener `return_against` apuntando al CCF.

### Checklist de datos maestros antes de emitir ND

> **Crítico**: el schema `fe-nd-v3.json` aplica restricciones de municipio más estrictas que CCF/NC.
> Un dato inválido produce `HTTP 422` en el gateway, no en MH.

- [ ] `return_against` apunta a un Sales Invoice de tipo CCF (no FE, no NC)
- [ ] El CCF origen tiene `sv_dte_generation_code` (UUID) y `sv_estado_mh = PROCESADO`
- [ ] Customer tiene `sv_nit`, `sv_nrc`, `sv_cod_actividad`, `sv_desc_actividad`, `sv_direccion_complemento`
- [ ] `sv_direccion_departamento` del Customer es un código válido (01-14)
- [ ] `sv_direccion_municipio` del Customer es compatible con su departamento según schema ND:
  - Dept 05 (La Libertad): municipio 01-22 (no 23-29)
  - Dept 01 (Santa Ana): municipio 01-12
  - Regla general: La Libertad tiene 22 municipios, otros departamentos pueden tener menos
- [ ] Establecimiento activo en `SV DTE Establishment`: `departamento=05`, `municipio` ≤ 22
- [ ] `cod_estable_mh` y `cod_punto_venta_mh` coinciden con lo registrado en MH

> **Nota**: CCF/NC aceptan hasta municipio 29 para dept 05; ND solo acepta hasta 22.
> Si un Customer fue configurado para CCF/NC con municipio 23-29 en dept 05, debe corregirse antes de emitir ND contra él.

### Pasos:
1. Crear Sales Invoice con `Is Return = 1` y `Return Against = <nombre-CCF>`.
2. Seleccionar `sv_dte_document_type = ND`.
3. Hacer clic en **DTE El Salvador → Emitir DTE**.
4. Verificar `sv_dte_control_number` empieza con `DTE-06-`.

### Restricción de esta implementación:
- ND solo puede referenciar CCF (tipo 03). No acepta FE (tipo 01).
- El schema MH acepta `tipoDocumento = "03"` o `"07"` — nuestra implementación solo usa "03".
- FE, CCF, NC, invalidación y contingencia no se vieron afectadas por los fixes ND (Sprint 6).

### Smoke test ND:
```bash
CCF_GEN_CODE=<uuid-del-ccf> bash apps/dte-gateway/tests/smoke/smoke_nd.sh
```

Ver §12 para el flujo completo de smoke tests CCF → NC → ND.

---

## 14. QR y Print Format

### Configurar URL de verificación MH:
1. ERPNext → **SV DTE Settings** → campo **URL Consulta Pública MH**.
2. Ingresar la URL base del portal de verificación del MH (confirmar con documentación oficial antes de producción).
3. Guardar.

Después de emitir un DTE, el campo `sv_dte_qr_url` se poblará automáticamente con la URL parametrizada.

### Botón "Ver en Hacienda":
- Aparece en Sales Invoice cuando `sv_dte_qr_url` está poblada.
- Abre la URL en nueva pestaña.

### Imprimir con Print Format DTE:
1. Sales Invoice enviada → **Imprimir** → seleccionar **"DTE El Salvador"**.
2. Incluye: tipo DTE, código generación, N° control, ítems, totales, sello MH.
3. Si `sv_dte_qr_url` está poblada: se muestra la URL de verificación en el pie.
4. Imagen QR pendiente para Sprint 8 (requiere confirmar URL oficial MH + elegir librería).

---

## 15. Emisión automática on_submit

### Activar:
1. ERPNext → **SV DTE Settings** → activar **"Emitir DTE automáticamente al someter"**.
2. Guardar.

### Comportamiento:
- Solo aplica a **FE y CCF**. NC, ND, contingencia e invalidación NO se auto-emiten.
- Si el DTE ya fue emitido (`sv_dte_generation_code` presente): no hace nada (idempotente).
- En éxito: el `sv_dte_generation_code` aparece al recargar el formulario. Sin popup.
- En fallo: se registra en **Error Log** (ERPNext → Buscar "Error Log") y aparece un aviso naranja no bloqueante. El submit NO se revierte.

### Diagnóstico de fallo:
1. ERPNext → **Error Log** → filtrar por `[DTE] Auto-emit fallido`.
2. El campo `message` contiene la excepción completa.
3. Corregir la causa y usar **"Emitir DTE"** manualmente.

---

## 16. Checklist emisión manual

Antes de emitir cualquier DTE desde la UI:

- [ ] Sales Invoice en estado **Enviada** (docstatus=1)
- [ ] `sv_dte_document_type` seleccionado (FE / CCF / NC / ND)
- [ ] Para CCF/NC/ND: Customer tiene `sv_nit`, `sv_nrc`, `sv_cod_actividad`, `sv_desc_actividad`, `sv_direccion_*` y `sv_correo` configurados
- [ ] Para NC/ND: `return_against` apunta a un CCF **PROCESADO** con `sv_dte_generation_code` presente
- [ ] Para ND: `sv_direccion_municipio` del Customer ≤ 22 si `sv_direccion_departamento=05` (ver §13)
- [ ] Gateway online: `curl http://localhost:8100/health`
- [ ] Firmador online y certificado vigente

---

## 17. Checklist emisión automática on_submit

- [ ] `emitir_al_someter=1` activado en **SV DTE Settings**
- [ ] Solo aplica a **FE y CCF** — NC y ND requieren emisión manual
- [ ] Si el DTE ya fue emitido (`sv_dte_generation_code` presente): no re-emite (idempotente)
- [ ] En fallo: **Error Log** → filtrar `[DTE] Auto-emit fallido` → corregir causa → usar "Emitir DTE" manual
- [ ] El submit **no se bloquea** aunque la emisión falle — el documento queda enviado sin DTE

---

## 18. Checklist Go-Live Producción

### Pre-deploy:
- [ ] Configurar `DTE_AMBIENTE=01` en `apps/dte-gateway/.env`
- [ ] Configurar credenciales PROD: `MH_API_PASSWORD`, `FIRMADOR_PASSWORD_PRI`, `NIT_EMISOR`
- [ ] Confirmar URL oficial del portal de verificación MH y configurar `url_verificacion_mh` en SV DTE Settings
- [ ] Hacer backup de `dte_store.db` antes de migrar
- [ ] Ejecutar `bench migrate` en ERPNext
- [ ] Reiniciar gateway: `docker restart dte-gateway`
- [ ] Verificar municipio de todos los Customers con `sv_direccion_departamento=05` — deben tener municipio ≤ 22 si emitirán ND (ver §13)
- [ ] Hacer benchmark en amb=00: emitir FE + CCF + NC + ND antes de subir a amb=01

### Post-deploy:
- [ ] Verificar health: `curl http://localhost:8100/health`
- [ ] Emitir una FE de prueba en ambiente PROD — verificar `sv_estado_mh = PROCESADO`
- [ ] Monitorear **Error Log** en ERPNext las primeras 24h
- [ ] Verificar que `sv_dte_qr_url` se genera correctamente (si `url_verificacion_mh` configurada)

### Backup y rollback:

```bash
# Backup gateway store (antes de cada actualización)
cp apps/dte-gateway/dte_store.db backups/dte_store_$(date +%Y%m%d).db

# Rollback gateway (stateless config — solo reiniciar con imagen anterior)
docker restart dte-gateway

# Rollback ERPNext patch (si bench migrate falla)
bench --site development.localhost migrate --rollback
```

### Riesgos documentados:
| Riesgo | Nivel | Mitigación |
|--------|-------|------------|
| URL de verificación MH no confirmada oficialmente | ALTO | No configurar `url_verificacion_mh` hasta confirmar. El campo es opcional — la emisión no depende de él. |
| `dte_store.db` sin backup automático | MEDIO | Copiar manualmente antes de actualizaciones del gateway |
| Schema ND (tipo 06) no probado en PROD aún | BAJO | Validada en homologación (Sprint 6): MH procesó con sello real. Probar en amb=00 antes de subir a PROD. Smoke test disponible. |
| Municipio de Customer incompatible con schema ND | MEDIO | ND exige municipio ≤ 22 para dept 05. Verificar checklist en §13 antes de emitir la primera ND en PROD. No es bug de código. |
