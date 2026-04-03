"""Logging estructurado para eventos DTE del gateway."""
import logging
from typing import Any

logger = logging.getLogger("dte_gateway")


def log_emit(
    docname: str,
    tipo_dte: str,
    ambiente: str,
    generation_code: str | None,
    status: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Registra un evento de emisión DTE."""
    logger.info(
        "DTE_EMIT docname=%s tipo=%s ambiente=%s gen_code=%s status=%s %s",
        docname,
        tipo_dte,
        ambiente,
        generation_code or "N/A",
        status,
        extra or {},
    )


def log_error(
    operation: str,
    docname: str | None,
    error: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Registra un error en una operación DTE."""
    logger.error(
        "DTE_ERROR op=%s docname=%s error=%s %s",
        operation,
        docname or "N/A",
        error,
        extra or {},
    )
