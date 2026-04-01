"""
cemevisa_scraper.py — Scraper para catálogo Cemevisa
Versión Requests+BeautifulSoup v2 — URLs con filtros reales

Estructura de URLs Cemevisa (verificada en DOM):
  /es/todo/todo/f-{FAMILIA}-0-{OFFSET}/c-{PALABRA}------{MARCA}---/
  
Filtro por texto: se añade segmento _te-{texto}/ al final
Filtro por marca: se añade segmento _ma-{marca_code},{marca_slug}/ al final
"""

from __future__ import annotations
import re
import requests
from bs4 import BeautifulSoup

# ── Códigos de familia (verificados en JS de Cemevisa) ─────────────────────────
FAMILIAS = {
    "hornos":         "000009",
    "horno":          "000009",
    "frio":           "frio",
    "nevera":         "frio",
    "frigorifico":    "frio",
    "congelador":     "frio",
    "lavadora":       "000002",
    "lavadoras":      "000002",
    "lavado":         "000002",
    "lavavajillas":   "000003",
    "placas":         "placas",
    "placa":          "placas",
    "campana":        "000007",
    "campanas":       "000007",
    "microondas":     "001425",
    "microonda":      "001425",
    "secadora":       "000002",
    "secadoras":      "000002",
    "horno_compacto": "000009",
}

# ── Códigos de marca (código_cemevisa, slug) ───────────────────────────────────
MARCAS = {
    "balay":      ("bsh49", "balay"),
    "bosch":      ("bshb2", "bosch"),
    "siemens":    ("bshs3", "siemens"),
    "aeg":        ("ge39",  "aeg"),
    "electrolux": ("ge08",  "electrolux"),
    "cata":       ("cna38", "cata"),
    "teka":       ("tek11", "teka"),
    "beko":       ("bek01", "beko"),
    "hisense":    ("his01", "hisense"),
    "samsung":    ("sam01", "samsung"),
    "lg":         ("lg001", "lg"),
    "whirlpool":  ("whi01", "whirlpool"),
    "neff":       ("bshn1", "neff"),
    "candy":      ("can01", "candy"),
    "edesa":      ("ede01", "edesa"),
}

BASE_URL = "https://www.cemevisa.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}


def _build_url(familia_code: str, marca_code: str = "", marca_slug: str = "",
               palabra: str = "", offset: int = 0) -> str:
    """
    Construye la URL de catálogo filtrada de Cemevisa.
    
    Patrón base: /es/todo/todo/f-{FAMILIA}-0-{OFFSET}/
    Filtro texto: se añade _te-{texto}/ 
    Filtro marca: se añade _ma-{marca_code},{marca_slug}/
    """
    base = f"{BASE_URL}/es/todo/todo/f-{familia_code}-0-{offset}/"
    
    filters = []
    if palabra and palabra.strip():
        palabra_url = palabra.strip().replace(" ", "%20").lower()
        filters.append(f"_te-{palabra_url}")
    if marca_code:
        filters.append(f"_ma-{marca_code},{marca_slug}")
    
    if filters:
        base += "/".join(filters) + "/"
    
    return base


def _parse_precio(precio_raw: str) -> float | None:
    """Convierte '306,00€' → 306.0"""
    try:
        limpio = precio_raw.replace("€", "").replace(".", "").replace(",", ".").strip()
        return float(limpio)
    except Exception:
        return None


def _login(session: requests.Session, usuario: str, clave: str) -> bool:
    """Realiza el login en Cemevisa y devuelve True si fue exitoso."""
    try:
        r = session.get(BASE_URL, headers=HEADERS, timeout=20)
        login_data = {
            "Tusuario": usuario,
            "Tclave": clave,
            "accion": "login",
        }
        r = session.post(f"{BASE_URL}/es/usuarios/identificar/",
                         data=login_data, headers=HEADERS, timeout=20, allow_redirects=True)
        return "logout" in r.text.lower() or usuario in r.text
    except Exception:
        return False


def _extract_page_products(html: str) -> list[dict]:
    """Extrae productos del HTML de una página de listado de Cemevisa."""
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr.bloque")
    products = []
    
    for row in rows:
        # ── Nombre y enlace ──
        enlace = row.select_one("td.tres-col a.tt")
        titular = row.select_one("td.tres-col a.tt p.titular")
        
        if not enlace:
            continue
        
        href = enlace.get("href", "")
        if not href.startswith("http"):
            href = BASE_URL + href
        
        nombre = titular.get_text(strip=True) if titular else enlace.get_text(" ", strip=True)
        
        # ── Referencia ──
        ref_match = re.search(r"/p-([^/]+)/", href)
        referencia = ref_match.group(1) if ref_match else "—"
        
        # ── Precio neto ──
        precio_el = row.select_one("td.precioneto")
        precio_raw = precio_el.get_text(strip=True) if precio_el else ""
        
        if not nombre or not precio_raw:
            continue
        
        # ── Imagen ──
        img_el = row.select_one("a.tt div img")
        img_src = ""
        if img_el:
            img_src = img_el.get("src", "") or img_el.get("data-src", "")
            if img_src and not img_src.startswith("http"):
                img_src = BASE_URL + img_src
        
        # ── Descripción / Características rápidas ──
        # Cemevisa muestra bullets de características debajo del nombre
        desc_items = row.select("td.tres-col ul li")
        descripcion = " · ".join([li.get_text(strip=True) for li in desc_items if li.get_text(strip=True)])
        
        # Si no hay bullets, intentar coger el texto pequeño
        if not descripcion:
            desc_el = row.select_one("td.tres-col p.subtitular")
            if desc_el:
                descripcion = desc_el.get_text(strip=True)
        
        products.append({
            "nombre":      nombre,
            "referencia":  referencia,
            "precio_raw":  precio_raw,
            "url":         href,
            "imagen":      img_src,
            "descripcion": descripcion,
        })
    
    return products


async def buscar_cemevisa(
    usuario: str,
    clave: str,
    familia: str,
    marca: str | None = None,
    palabra: str = "",
    margen: float = 0.40,
    max_paginas: int = 3,
    headless: bool = True,
) -> list[dict]:
    """
    Busca productos en Cemevisa usando requests+BeautifulSoup.
    Usa los filtros de URL nativos de Cemevisa (_te- para texto, _ma- para marca).
    """
    familia_lower = familia.lower().strip()
    familia_code = FAMILIAS.get(familia_lower, "")
    if not familia_code:
        raise ValueError(f"Familia '{familia}' no reconocida. Opciones: {list(FAMILIAS.keys())}")

    marca_code = ""
    marca_slug = ""
    if marca:
        marca_info = MARCAS.get(marca.lower().strip())
        if marca_info:
            marca_code, marca_slug = marca_info

    session = requests.Session()
    session.headers.update(HEADERS)

    # Login
    logged_in = _login(session, usuario, clave)
    if not logged_in:
        # Intentar una vez más
        _login(session, usuario, clave)

    # Scraping por páginas
    todos_productos = []

    for pagina in range(max_paginas):
        offset = pagina * 20
        url = _build_url(familia_code, marca_code, marca_slug, palabra, offset)

        try:
            r = session.get(url, timeout=25, allow_redirects=True)
            if r.status_code != 200:
                break
            productos_pagina = _extract_page_products(r.text)
        except Exception:
            break

        if not productos_pagina:
            break

        todos_productos.extend(productos_pagina)

        # Comprobar paginación
        soup = BeautifulSoup(r.text, "html.parser")
        pag_text = soup.select_one(".pagination p")
        if pag_text:
            match = re.search(r"página (\d+) de (\d+)", pag_text.get_text())
            if match and int(match.group(1)) >= int(match.group(2)):
                break

    # Calcular precios con margen
    resultados = []
    for p in todos_productos:
        coste = _parse_precio(p["precio_raw"])
        if coste is None:
            continue
        pvp = round(coste / (1 - margen), 2)
        beneficio = round(pvp - coste, 2)
        resultados.append({
            "Referencia":   p["referencia"],
            "Nombre":       p["nombre"],
            "Descripcion":  p["descripcion"],
            "Coste €":      coste,
            "PVP €":        pvp,
            "Beneficio €":  beneficio,
            "URL":          p["url"],
            "Imagen":       p["imagen"],
            "Fuente":       "Cemevisa",
        })

    # Filtro post-search para "horno_compacto"
    if familia_lower == "horno_compacto":
        resultados = [r for r in resultados if "45" in r["Nombre"] or "COMPACT" in r["Nombre"].upper()]

    return sorted(resultados, key=lambda x: x["Beneficio €"], reverse=True)


# ── Test directo ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    async def main():
        resultados = await buscar_cemevisa(
            usuario="13323",
            clave="2h74",
            familia="hornos",
            marca="balay",
            palabra="",
            margen=0.40,
            max_paginas=2,
        )
        print(f"\n✅ {len(resultados)} productos encontrados\n")
        for r in resultados[:10]:
            print(f"  {r['Referencia']:15} | {r['Nombre'][:45]:45} | {r['Coste €']:.2f}€ | {r['Descripcion'][:50]}")
    asyncio.run(main())
