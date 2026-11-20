"""Redacción del borrador del informe de reparación con la API de Claude.

Se llama por HTTPS directo (``requests``) y no con la librería ``anthropic`` a
propósito: el Python de este servidor es el del sistema y lo comparte con Odoo,
y se decidió no instalar nada nuevo en producción.
"""
import json
import logging
import os

import requests

_logger = logging.getLogger(__name__)

API_URL = "https://api.anthropic.com/v1/messages"
MODELO_POR_DEFECTO = "claude-opus-5-5"
FICHERO_CLAVE_POR_DEFECTO = "/opt/odoo/secrets/anthropic_api_key"

CAMPOS_TEXTO = (
    "averia_comunicada",
    "diagnostico",
    "trabajo_realizado",
    "piezas_sustituidas",
    "recomendaciones",
    "pendiente",
)

ESQUEMA = {
    "type": "object",
    "properties": {
        "suficiente": {
            "type": "boolean",
            "description": "true si las notas describen qué se le ha hecho a la "
            "máquina (o que se revisó y no presenta fallo).",
        },
        "motivo_insuficiente": {"type": "string"},
        "averia_comunicada": {"type": "string"},
        "diagnostico": {"type": "string"},
        "trabajo_realizado": {"type": "string"},
        "piezas_sustituidas": {"type": "string"},
        "recomendaciones": {"type": "string"},
        "pendiente": {"type": "string"},
        "avisos_revision": {"type": "string"},
    },
    "required": [
        "suficiente",
        "motivo_insuficiente",
        "averia_comunicada",
        "diagnostico",
        "trabajo_realizado",
        "piezas_sustituidas",
        "recomendaciones",
        "pendiente",
        "avisos_revision",
    ],
    "additionalProperties": False,
}

SISTEMA = """\
Redactas informes de reparación para los clientes del servicio técnico de una \
empresa española que vende y repara aparatología de estética (centros de \
belleza y peluquerías). El informe se entrega al cliente en PDF junto con su \
máquina reparada. Antes de enviarse lo revisa una persona de la empresa.

Recibes los datos de un ticket del taller: el asunto, la descripción inicial y \
las notas que el personal ha ido escribiendo, por orden de fecha. Esas notas \
son apuntes de trabajo, no están pensadas para el cliente: mezclan lo que se le \
ha hecho a la máquina con gestiones internas.

Lo que más importa:

- Usa solo lo que está escrito en el ticket. El cliente va a leer esto como la \
verdad de lo que se le ha hecho a su máquina, así que no añadas piezas, \
comprobaciones, causas ni recomendaciones que las notas no respalden. Si un \
apartado no tiene contenido, déjalo como cadena vacía; un apartado vacío es \
correcto y uno inventado no.
- Deja fuera las gestiones internas: llamadas o mensajes sin respuesta, citas \
de entrega, falta de material en el almacén, comentarios entre compañeros, \
precios y cualquier nombre de persona.
- Cuando el técnico supone la causa de la avería (sobre todo si apunta a un mal \
uso por parte del cliente), no lo afirmes como un hecho en el informe. Describe \
lo que se encontró en la máquina y, si procede, convierte la causa probable en \
una recomendación de uso neutra. Menciona esa decisión en avisos_revision para \
que la persona que revisa decida.
- Si la máquina se revisó y no presentó fallo, eso es un resultado válido: \
explica qué se comprobó y que funciona correctamente.

Apartados:

- averia_comunicada: el problema por el que la máquina entró en el taller.
- diagnostico: lo que el técnico encontró al revisarla.
- trabajo_realizado: lo que se hizo (reparaciones, sustituciones, ajustes, \
limpieza, pruebas).
- piezas_sustituidas: las piezas o componentes cambiados, una por línea. Vacío \
si no se cambió nada.
- recomendaciones: consejos de uso o mantenimiento que se desprendan de las notas.
- pendiente: lo que el técnico ha dejado dicho que queda por resolver en una \
próxima visita.
- avisos_revision: notas para la persona que revisa, que no se imprimen: dudas, \
contradicciones entre notas, suposiciones que has suavizado o datos que has \
dejado fuera y quizá convenga incluir. Vacío si no hay nada que señalar.

suficiente: ponlo a false cuando las notas no permitan decirle al cliente qué \
se le ha hecho a su máquina (no hay ninguna nota de intervención, o solo hay \
gestiones). En ese caso explica en motivo_insuficiente, en una frase dirigida \
al técnico, qué falta, y deja los demás apartados vacíos.

Estilo: castellano de España, claro y profesional, en frases completas, con \
trato de usted y sin jerga de taller. Corrige erratas y nombres de piezas mal \
escritos cuando el sentido sea evidente. Texto plano, sin Markdown. Sé breve: \
cada apartado ocupa lo que su contenido necesite, normalmente entre una y \
cuatro frases.
"""


class ErrorInformeIA(Exception):
    """Fallo al pedir el borrador. ``reintentable`` indica si merece otro intento."""

    def __init__(self, mensaje, reintentable=True):
        super().__init__(mensaje)
        self.reintentable = reintentable


def leer_clave(ruta):
    ruta = ruta or FICHERO_CLAVE_POR_DEFECTO
    if not os.path.isfile(ruta):
        raise ErrorInformeIA(
            "Falta la clave de la API de Claude (no existe %s)." % ruta, reintentable=False
        )
    with open(ruta) as fichero:
        clave = fichero.read().strip()
    if not clave:
        raise ErrorInformeIA(
            "El fichero de la clave de la API de Claude está vacío (%s)." % ruta,
            reintentable=False,
        )
    return clave


def redactar(datos_ticket, clave, modelo=None, timeout=180):
    """Devuelve el dict del borrador (claves de ESQUEMA) a partir del texto del ticket."""
    cuerpo = {
        "model": modelo or MODELO_POR_DEFECTO,
        "max_tokens": 16000,
        "system": SISTEMA,
        "output_config": {
            "effort": "medium",
            "format": {"type": "json_schema", "schema": ESQUEMA},
        },
        # Si el modelo declina por un filtro de seguridad, la API lo reintenta
        # sola en el modelo de reserva que corresponda.
        "fallbacks": "default",
        "messages": [{"role": "user", "content": datos_ticket}],
    }
    cabeceras = {
        "x-api-key": clave,
        "anthropic-version": "2026-10-21",
        "anthropic-beta": "server-side-fallback-2026-07-01",
        "content-type": "application/json",
    }
    try:
        respuesta = requests.post(API_URL, headers=cabeceras, json=cuerpo, timeout=timeout)
    except requests.RequestException as error:
        raise ErrorInformeIA("No se pudo conectar con la API de Claude: %s" % error)

    if respuesta.status_code != 200:
        try:
            detalle = respuesta.json().get("error", {}).get("message", "")
        except ValueError:
            detalle = respuesta.text[:300]
        reintentable = respuesta.status_code in (408, 409, 429) or respuesta.status_code >= 500
        raise ErrorInformeIA(
            "La API de Claude respondió %s: %s" % (respuesta.status_code, detalle),
            reintentable=reintentable,
        )

    mensaje = respuesta.json()
    motivo = mensaje.get("stop_reason")
    if motivo == "refusal":
        raise ErrorInformeIA("El modelo ha declinado redactar este informe.", reintentable=False)
    if motivo == "max_tokens":
        raise ErrorInformeIA("La respuesta del modelo se cortó por longitud.", reintentable=False)
    texto = next((b.get("text") for b in mensaje.get("content", []) if b.get("type") == "text"), None)
    if not texto:
        raise ErrorInformeIA("La respuesta del modelo no trae texto.")
    try:
        borrador = json.loads(texto)
    except ValueError:
        raise ErrorInformeIA("La respuesta del modelo no es JSON válido.")
    _logger.info(
        "Informe de reparación redactado con %s (%s)", mensaje.get("model"), mensaje.get("usage")
    )
    return borrador
