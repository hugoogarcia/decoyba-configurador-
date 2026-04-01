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

SYSTEM_PROMPT = f"""Eres un asistente experto de DECOYBA (electrodomésticos).
Tu misión: extraer parámetros de búsqueda de electrodomésticos en JSON.

Familias válidas: {', '.join(FAMILIAS_VALIDAS)}
Marcas válidas:   {', '.join(MARCAS_VALIDAS)}

JSON esperado (responde SOLO con el JSON, sin texto adicional):
{{
  "familia":   "<familia_válida>",
  "marca":     "<marca_válida_o_null>",
  "calidad":   "baja" | "media" | "alta",
  "margen":    <float entre 0.20 y 0.60>,
  "palabra":   "<términos_extra_para_filtrar>",
  "barato":    true | false,
  "premium":   true | false
}}

Reglas CRÍTICAS de interpretación:
1. "familia": 
   - "lavavajillas" → familia="lavavajillas"
   - "lavadora", "lavadoras", "lavado" → familia="lavadora"
   - "horno", "hornos" → familia="hornos"
   - "nevera", "frigo", "frigorifico" → familia="frio"
   - Si pide "compacto" o "45 cm" con hornos → familia="horno_compacto"
   - "campana", "extractor" → familia="campana"
   - "placa", "placas", "inducción" → familia="placas"
   - "microondas" → familia="microondas"
   - "secadora" → familia="secadora"

2. "palabra": Extrae SOLO los atributos técnicos útiles para filtrar:
   - Capacidad: "7kg", "8kg", "60cm", "45cm", etc. → inclúyelos tal cual
   - Características: "inducción", "pirolítico", "integrable", "libre instalación"
   - NO incluyas la familia ni la marca en "palabra"
   - Ejemplo: "lavadora bosch 7kg carga frontal" → palabra="7kg carga frontal"
   - Ejemplo: "lavavajillas barato 60cm" → familia="lavavajillas", palabra="60cm"
   - Si no hay atributos extra → palabra=""

3. "barato": true si pide expresamente 'barato', 'económico', 'oferta', 'el más bajo'.
4. "premium": true si pide 'calidad', 'mejor', 'premium', 'tope de gama', 'gama alta'.
5. "margen" sugerido: baja=0.30, media=0.40, alta=0.50.
6. Si pide "pirolítico" → inclúyelo en "palabra" como "pirolitico" (sin tilde).
7. "calidad": 
   - 'baja' = solo precio, económico, básico.
   - 'media' = equilibrado.
   - 'alta' = gama alta, premium.

EJEMPLOS:
- "lavavajillas baratas" → {{"familia":"lavavajillas","marca":null,"calidad":"baja","margen":0.30,"palabra":"","barato":true,"premium":false}}
- "lavadora 7kg bosch" → {{"familia":"lavadora","marca":"bosch","calidad":"media","margen":0.40,"palabra":"7kg","barato":false,"premium":false}}
- "horno siemens pirolítico" → {{"familia":"hornos","marca":"siemens","calidad":"alta","margen":0.45,"palabra":"pirolitico","barato":false,"premium":true}}
- "frigorífico balay integrable" → {{"familia":"frio","marca":"balay","calidad":"media","margen":0.40,"palabra":"integrable","barato":false,"premium":false}}
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
