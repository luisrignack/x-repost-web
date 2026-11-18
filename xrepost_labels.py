#!/usr/bin/env python3
"""Etiquetas de resultado compartidas por el motor, el CLI y el panel web.

`xrepost.py` no puede importar módulos del proyecto de la forma habitual
(se ejecuta dentro del harness, leyendo el script por stdin y sin `__file__`),
así que `xrepost.sh` exporta `X_SELF_DIR` y el motor añade esa carpeta a
`sys.path` antes de importar este archivo.
"""

from __future__ import annotations

# Códigos internos (historial) → texto que ve el usuario.
LABELS = {
    "reposted": "reposteado",
    "quoted": "citado con comentario",
    "already": "ya estaba reposteado",
    "no_button": "no encontré el botón de repost",
    "no_menu": "el menú no se abrió",
    "no_quote_option": "el menú no ofrecía «Citar»",
    "no_composer": "no se abrió el editor de la cita",
    "quote_failed": "no se pudo publicar la cita",
    "quote_unverified": "cita sin confirmar (revisa tu perfil)",
    "unconfirmed": "no se pudo confirmar (revisa tu perfil)",
    "undone": "deshecho",
    "not_reposted": "no estaba reposteado",
    "undo_failed": "no se pudo deshacer",
    # Bloqueos de la propia página de X: se detiene la tanda.
    "session_expired": "la sesión de X caducó (inicia sesión en Chrome)",
    "captcha": "X pidió una verificación humana",
    "rate_limited": "X limitó las solicitudes (espera antes de reintentar)",
    "suspended": "la cuenta aparece suspendida o restringida",
    "page_unavailable": "la publicación o la página no está disponible",
    "navigation_failed": "no se pudo abrir la publicación",
    # Resultados de filtros (no son fallos del motor).
    "filtered_lang": "descartado por idioma",
    "filtered_media": "descartado por tipo de contenido",
    "filtered_length": "descartado por longitud",
    "filtered_regex": "descartado por expresión regular",
    "skipped_uncertain": "omitido: un intento anterior quedó sin confirmar",
    "skipped_history": "omitido: ya consta en el historial",
}

# Estados que no se reintentan automáticamente en otra ejecución.
UNCERTAIN_RESULTS = ("unconfirmed", "quote_unverified")

# Estados que obligan a detener toda la tanda.
FATAL_RESULTS = ("session_expired", "captcha", "rate_limited", "suspended")


def label(result: str) -> str:
    """Texto visible de un resultado; si no está etiquetado, el código crudo."""
    return LABELS.get(result, result)
