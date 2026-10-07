"""Formato JSON estandarizado para toda la API."""
import logging

from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("clinica")


class RenderizadorEstandar(JSONRenderer):
    """
    Envuelve las respuestas exitosas:
        {"ok": true, "status": 200, "datos": ...}
    Los errores ya vienen con el formato {"ok": false, ...} desde manejador_excepciones.
    """

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = (renderer_context or {}).get("response")
        if (
            response is not None
            and data is not None
            and response.status_code < 400
            and not (isinstance(data, dict) and "ok" in data)
        ):
            data = {"ok": True, "status": response.status_code, "datos": data}
        return super().render(data, accepted_media_type, renderer_context)


def manejador_excepciones(exc, context):
    """
    Respuestas de error uniformes:
        {"ok": false, "status": 400, "errores": {...}}
    Los errores inesperados devuelven 500 sin filtrar detalles internos.
    """
    response = exception_handler(exc, context)
    if response is not None:
        response.data = {"ok": False, "status": response.status_code, "errores": response.data}
        return response

    logger.exception("Error no controlado en la vista", exc_info=exc)
    return Response(
        {
            "ok": False,
            "status": 500,
            "errores": {"detail": "Ocurrió un error interno en el servidor."},
        },
        status=500,
    )
