"""
dte_service — Orquestador del flujo de emisión DTE.

Flujo:
  0. Idempotencia — devolver cached si ya completó
  1. Identificadores (codigoGeneracion + numeroControl)
  2. Build DTE JSON (mapper según tipo)
  3. Schema validation — BLOQUEANTE (ValueError si hay errores)
  4. Firma (signer_client — password_pri via secret_resolver)
  5. Auth token (auth_client — api_password via secret_resolver)
  6. Transmisión MH (mh_client — retry 3x)
  7. Persistir idempotencia como 'completed'
  8. Retornar DTEEmitResponse

El secuencial NO se revierte si el proceso falla después del paso 1.
"""

import logging

from app.models.dte_request import DTEEmitRequest
from app.models.dte_response import DTEEmitResponse
from app.services import auth_client, mh_client, signer_client
from app.services.control_number import generate_codigo_generacion, generate_numero_control
from app.services.dte_store import check_idempotency, next_secuencial, save_idempotency
from app.services.mappers.ccf_mapper import build_ccf
from app.services.mappers.fe_mapper import build_fe
from app.services.mappers.nc_mapper import build_nc
from app.services.mappers.nd_mapper import build_nd
from app.services.schema_validator import validate_dte

logger = logging.getLogger(__name__)

_MAPPERS = {
    "01": build_fe,
    "03": build_ccf,
    "05": build_nc,
    "06": build_nd,   # Nota de Débito (tipoDte="06" confirmado en fe-nd-v3.json)
}


def emit(request: DTEEmitRequest) -> DTEEmitResponse:
    """
    Emite un DTE end-to-end: build → validate → sign → auth → transmit → cache.

    Raises:
        ValueError: schema inválido o colisión de idempotencia.
        RuntimeError: fallo en firmador, MH o secretos no configurados.
        KeyError: tipo_dte no soportado.
    """
    s = request.emisor
    key = request.idempotency_key

    # 0. Idempotencia — cache hit
    cached = check_idempotency(key, request.tipo_dte, request.ambiente, s.nit)
    if cached:
        logger.info("dte_service: idempotency hit key=%s", key)
        return DTEEmitResponse(**cached)

    save_idempotency(key, "pending", request.tipo_dte, request.ambiente, s.nit)

    try:
        # 1. Identificadores
        gen_code = generate_codigo_generacion()
        secuencial = next_secuencial(request.tipo_dte, s.cod_estable_mh, s.cod_punto_venta_mh)
        num_ctrl = generate_numero_control(
            tipo_dte=request.tipo_dte,
            cod_estable_mh=s.cod_estable_mh,
            cod_punto_venta_mh=s.cod_punto_venta_mh,
            secuencial=secuencial,
        )
        logger.info(
            "dte_service: emit tipo=%s docname=%s gen_code=%s num_ctrl=%s",
            request.tipo_dte, request.docname, gen_code, num_ctrl,
        )

        # 2. Build DTE JSON
        mapper = _MAPPERS.get(request.tipo_dte)
        if mapper is None:
            raise KeyError(f"tipo_dte no soportado: {request.tipo_dte!r}")
        dte_json = mapper(request, num_ctrl, gen_code)

        # 3. Schema validation — BLOQUEANTE
        if not request.skip_schema_validation:
            errors = validate_dte(dte_json, request.tipo_dte)
            if errors:
                raise ValueError(
                    f"DTE {request.tipo_dte} inválido según schema MH "
                    f"({len(errors)} error(es)): {'; '.join(errors[:5])}"
                )

        # 4. Firma — el JWS es el documento firmado completo
        jws = signer_client.sign_dte(dte_json, s.nit, s.url_firmador, firmador_nit=s.nit_firmador)

        # 5. Auth token
        token = auth_client.get_token(s.nit, request.ambiente)

        # 6. Transmisión MH — body wrapper con JWS, no el DTE completo
        version = dte_json["identificacion"]["version"]
        mh_resp = mh_client.send_dte(
            jws=jws,
            codigo_generacion=gen_code,
            tipo_dte=request.tipo_dte,
            version=version,
            ambiente=request.ambiente,
            token=token,
        )

        estado = mh_resp.get("estado", "")
        response = DTEEmitResponse(
            status="procesado" if estado == "PROCESADO" else "rechazado",
            mode="live",
            generation_code=gen_code,
            uuid_dte=gen_code,
            control_number=num_ctrl,
            estado=estado,
            sello_recibido=mh_resp.get("selloRecibido"),
            fh_procesamiento=mh_resp.get("fhProcesamiento"),
            clasifica_msg=mh_resp.get("clasificaMsg"),
            codigo_msg=mh_resp.get("codigoMsg"),
            observaciones=mh_resp.get("observaciones") or [],
        )

        # 7. Persistir idempotencia
        save_idempotency(key, "completed", request.tipo_dte, request.ambiente, s.nit, response.model_dump())
        logger.info(
            "dte_service: completado docname=%s estado=%s sello=%s",
            request.docname, estado, response.sello_recibido,
        )
        return response

    except Exception as exc:
        save_idempotency(key, "failed", request.tipo_dte, request.ambiente, s.nit)
        logger.error("dte_service: fallo docname=%s tipo=%s: %s", request.docname, request.tipo_dte, exc)
        raise
