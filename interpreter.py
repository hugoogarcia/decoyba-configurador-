"""
interpreter.py — Interpreta consultas en lenguaje natural usando OpenAI API
Convierte texto libre en parámetros de búsqueda detallados para Cemevisa y Gocisa.
"""

from __future__ import annotations
import openai
import json
import re
import os

# Familias y marcas válidas
FAMILIAS_VALIDAS = [
    "hornos", "frio", "nevera", "frigorifico", "congelador",
    "lavadora", "lavadoras", "lavavajillas", "placas", "placa",
    "campana", "campanas", "microondas", "secadora", "secadoras",
    "horno_compacto",
]

MARCAS_VALIDAS = [
    "balay", "bosch", "siemens", "aeg", "electrolux",
    "cata", "teka", "beko", "hisense", "samsung", "lg",
    "whirlpool", "neff", "candy", "edesa", "smeg", "elica",
]

SYSTEM_PROMPT = f"""Eres un Ingeniero Comercial experto en electrodomésticos para DECOYBA.
Tu misión: extraer parámetros técnicos exactos de una consulta natural para alimentar scrapers industriales.

Familias válidas: {', '.join(FAMILIAS_VALIDAS)}
Marcas válidas:   {', '.join(MARCAS_VALIDAS)}

JSON ESPERADO:
{{
  "familia":   "<familia_extraída>",
  "marca":     "<marca_extraída_o_null>",
  "calidad":   "baja" | "media" | "alta",
  "margen":    <float: 0.30 (baja), 0.40 (media), 0.50 (alta)>,
  "palabra":   "<especificaciones_técnicas_como_7kg_inox_etc>",
  "barato":    true | false,
  "premium":   true | false,
  "razonamiento": "<breve_explicación_de_marketing>"
}}

REGLAS DE EXPERTO:
1. "familia": Mapeo estricto (lavavajillas, lavadora, frio, hornos, placas, campana, microondas, secadora).
2. "palabra": Extrae SOLO atributos técnicos (7kg, 8kg, 60cm, 45cm, inox, pirolitico, integrable). 
3. NO incluyas la marca ni la familia dentro de "palabra".
4. "calidad": 
   - 'baja' si pide "barato", "económico", "oferta".
   - 'alta' si pide "mejor", "premium", "calidad", "bosch", "siemens", "neff", "aeg".
5. Si no hay marca, marca=null. Si no hay palabra extra, palabra="".
"""


def interpretar(texto: str, margen_override: float | None = None) -> dict:
    """
    Interpreta una consulta en lenguaje natural y devuelve parámetros de búsqueda.

    Args:
        texto           : Consulta del usuario (ej: "lavadora bosch 7kg")
        margen_override : Si se especifica, sobreescribe el margen calculado por IA

    Returns:
        Dict con claves: familia, marca, calidad, margen, palabra, barato, premium
    """
    api_key = None
    try:
        import streamlit as st
        api_key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        api_key = os.environ.get("OPENAI_API_KEY")

    if api_key:
        try:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # más rápido y barato para esta tarea
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": texto}
                ],
                response_format={"type": "json_object"},
                temperature=0,
            )
            raw = response.choices[0].message.content.strip()
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not json_match:
                raise ValueError(f"IA no devolvió JSON válido: {raw}")
            params = json.loads(json_match.group())
        except Exception:
            # Fallback: interpretación local sin IA
            params = _interpretar_local(texto)
    else:
        # Sin API key: interpretación local
        params = _interpretar_local(texto)

    # Limpiar y normalizar
    params = _normalizar_params(params, texto)

    # Aplicar override de margen desde el slider
    if margen_override is not None:
        params["margen"] = round(margen_override, 2)

    # Validar familia
    if params.get("familia") not in FAMILIAS_VALIDAS:
        # Intentar deducir de la consulta original
        params["familia"] = _deducir_familia(texto) or "hornos"

    return params


def _normalizar_params(params: dict, texto_original: str) -> dict:
    """Normaliza y rellena defaults en los parámetros."""
    defaults = {
        "familia": "hornos",
        "marca": None,
        "calidad": "media",
        "margen": 0.40,
        "palabra": "",
        "barato": False,
        "premium": False,
    }
    for k, v in defaults.items():
        if k not in params or params[k] is None and k not in ("marca", "palabra"):
            params.setdefault(k, v)

    # Limpiar marca si no es válida
    if params.get("marca") and params["marca"].lower() not in MARCAS_VALIDAS:
        params["marca"] = None

    # Asegurar que la palabra no contiene marca ni familia
    if params.get("palabra") and params.get("marca"):
        params["palabra"] = params["palabra"].lower().replace(params["marca"].lower(), "").strip()
    if params.get("palabra") and params.get("familia"):
        params["palabra"] = params["palabra"].lower().replace(params["familia"].lower(), "").strip()

    return params


def _deducir_familia(texto: str) -> str | None:
    """Deducción básica de familia por palabras clave."""
    texto_low = texto.lower()
    mapping = {
        "lavavajilla": "lavavajillas",
        "lavadora":    "lavadora",
        "lavado":      "lavadora",
        "secadora":    "secadora",
        "horno":       "hornos",
        "campana":     "campana",
        "extractor":   "campana",
        "placa":       "placas",
        "inducció":    "placas",
        "microonda":   "microondas",
        "nevera":      "frio",
        "frigo":       "frio",
        "frigorifico": "frio",
        "congelador":  "congelador",
    }
    for key, familia in mapping.items():
        if key in texto_low:
            return familia
    return None


def _interpretar_local(texto: str) -> dict:
    """
    Interpretación local sin IA. Usa reglas simples de palabras clave.
    Fallback para cuando no hay API key o la llamada falla.
    """
    texto_low = texto.lower()
    
    # Familia
    familia = _deducir_familia(texto) or "hornos"
    if "compact" in texto_low or "45 cm" in texto_low:
        familia = "horno_compacto"
    
    # Marca
    marca = None
    for m in MARCAS_VALIDAS:
        if m in texto_low:
            marca = m
            break
    
    # Calidad / precio / premium
    barato = any(w in texto_low for w in ["barato", "económico", "economico", "oferta", "precio", "bajo"])
    premium = any(w in texto_low for w in ["premium", "gama alta", "lujo", "mejor", "calidad"])
    
    # Margen
    margen = 0.30 if barato else (0.50 if premium else 0.40)
    calidad = "baja" if barato else ("alta" if premium else "media")
    
    # Palabra: extraer lo que no es familia ni marca
    stop_words = {familia, marca or "", "el", "la", "lo", "un", "una",
                  "de", "que", "para", "con", "sin", "y", "o", "muy",
                  "barato", "economico", "económico", "premium", "mejor",
                  "calidad", "precio", "gama", "alta", "bajo", "oferta"}
    words = [w for w in texto_low.split() if w not in stop_words and len(w) > 2]
    # Conservar patrones como "7kg", "60cm"
    palabra = " ".join(words)
    
    return {
        "familia": familia,
        "marca":   marca,
        "calidad": calidad,
        "margen":  margen,
        "palabra": palabra,
        "barato":  barato,
        "premium": premium,
    }


# ── Test directo ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        "lavavajillas barata",
        "lavadora bosch 7kg",
        "horno siemens pirolítico",
        "nevera balay no frost integrable",
        "placa de inducción teka",
        "microondas integrable compacto",
    ]
    for t in tests:
        r = interpretar(t)
        print(f"'{t}' → {r}")
