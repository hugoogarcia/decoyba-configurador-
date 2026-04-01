"""
interpreter.py — Interpreta consultas en lenguaje natural usando Claude API
Convierte texto libre en parámetros de búsqueda para Cemevisa.
"""

from __future__ import annotations
import openai
import json
import re

# Familias y marcas válidas (debe coincidir con cemevisa_scraper.py)
FAMILIAS_VALIDAS = [
    "hornos", "frio", "nevera", "frigorifico",
    "lavadora", "lavavajillas", "placas", "campana",
    "microondas", "secadora", "horno_compacto"
]

MARCAS_VALIDAS = [
    "balay", "bosch", "siemens", "aeg", "electrolux",
    "cata", "teka", "beko", "hisense", "samsung", "lg",
    "whirlpool", "neff"
]

SYSTEM_PROMPT = f"""Eres un asistente experto de DECOYBA (reformas de alta gama).
Tu misión: extraer parámetros de búsqueda de electrodomésticos en JSON.

Familias válidas: {', '.join(FAMILIAS_VALIDAS)}
Marcas válidas:   {', '.join(MARCAS_VALIDAS)}

JSON esperado:
{{
  "familia":  "<familia_válida>",
  "marca":    "<marca_válida_o_null>",
  "calidad":  "baja" | "media" | "alta",
  "margen":   <float entre 0.20 y 0.60>,
  "palabra":  "<término_extra_o_cadena_vacía>",
  "barato":   true | false,
  "premium":  true | false
}}

Reglas de interpretación:
1. "calidad": 
   - 'baja' = solo precio, económico, básico.
   - 'media' = "barato pero bueno", "calidad-precio", equilibrado.
   - 'alta' = gama alta, premium, lujo, lo mejor.
2. "barato": true si pide expresamente 'barato', 'económico', 'oferta', 'el más bajo'.
3. "premium": true si pide 'calidad', 'mejor', 'premium', 'tope de gama'.
4. "margen" sugerido: baja=0.30, media=0.40, alta=0.50.
5. "palabra": Extrae términos como "inducción", "cristal negro", "pirolítico", "compacto".
6. Si pide "compacto" o "45 cm", usa familia='horno_compacto'.
7. Si pide "pirolitico", mantenlo en "palabra" para que el scraper aplique el filtro.
"""


def interpretar(texto: str, margen_override: float | None = None) -> dict:
    """
    Interpreta una consulta en lenguaje natural y devuelve parámetros de búsqueda.

    Args:
        texto           : Consulta del usuario (ej: "horno Balay barato pero bueno")
        margen_override : Si se especifica, sobreescribe el margen calculado por IA

    Returns:
        Dict con claves: familia, marca, calidad, margen, palabra
    """
    client = openai.OpenAI()

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": texto}
        ],
        response_format={"type": "json_object"}
    )

    raw = response.choices[0].message.content.strip()

    # Extraer JSON aunque venga con texto alrededor
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not json_match:
        raise ValueError(f"La IA no devolvió JSON válido: {raw}")

    params = json.loads(json_match.group())

    # Aplicar override de margen si se especificó desde el slider
    if margen_override is not None:
        params["margen"] = round(margen_override, 2)

    # Validar familia
    if params.get("familia") not in FAMILIAS_VALIDAS:
        raise ValueError(f"Familia no reconocida: {params.get('familia')}")

    return params


# ── Test directo ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        "quiero un horno Balay barato pero que sea bueno",
        "nevera Bosch de calidad para un piso de lujo",
        "lavavajillas que no sea muy caro, marca da igual",
        "placa de inducción Siemens alta gama",
        "campana extractora para cocina grande, precio ajustado",
    ]

    for t in tests:
        try:
            r = interpretar(t)
            print(f"\n📝 '{t}'")
            print(f"   → {r}")
        except Exception as e:
            print(f"\n❌ Error en '{t}': {e}")
