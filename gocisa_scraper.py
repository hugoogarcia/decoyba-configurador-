"""
gocisa_scraper.py — Scraper para catálogo Gocisa
Versión Requests+BeautifulSoup (compatible con Streamlit Cloud, sin Playwright)
"""

from __future__ import annotations
import re
import requests
from bs4 import BeautifulSoup

# ── Mapeo de categorías Gocisa ──────────────────────────────────────────────────
CATEGORIAS = {
    "hornos":         "23470-hornos",
    "horno":          "23470-hornos",
    "lavadoras":      "23480-lavadoras",
    "lavadora":       "23480-lavadoras",
    "lavado":         "23480-lavadoras",
    "lavavajillas":   "23490-lavavajillas",
    "microondas":     "23500-microondas",
    "microonda":      "23500-microondas",
    "frio":           "23440-frio",
    "nevera":         "23440-frio",
    "frigorifico":    "23440-frio",
    "campana":        "23400-campanas",
    "placas":         "23530-placas-induccion",
    "placa":          "23530-placas-induccion",
    "horno_compacto": "23760-horno-independiente-45-cm-alto",
    "secadora":       "23480-lavadoras",
}

# ── Mapeo de fabricantes Gocisa ─────────────────────────────────────────────────
FABRICANTES = {
    "aeg":        "aeg",
    "balay":      "balay",
    "beko":       "beko",
    "bosch":      "bosch",
    "cata":       "cata",
    "edesa":      "edesa",
    "electrolux": "electrolux",
    "elica":      "elica",
    "hisense":    "hisense",
    "siemens":    "siemens",
    "smeg":       "smeg",
    "teka":       "teka",
    "whirlpool":  "whirlpool",
}

BASE_URL = "http://grupo.gocisa.es"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}


def _parse_precio(precio_raw: str) -> float | None:
    """Convierte '62,99 € antes de IVA' → 62.99"""
    if not precio_raw:
        return None
    try:
        limpio = (precio_raw
                  .replace("antes de IVA", "")
                  .replace("IVA incl.", "")
                  .replace("IVA incl", "")
                  .replace("€", "")
                  .replace(".", "")
                  .replace(",", ".")
                  .strip())
        match = re.search(r"(\d+\.\d+|\d+)", limpio)
        if match:
            return float(match.group(1))
        return None
    except Exception:
        return None


def _extract_ref(nombre: str) -> str:
    """Intenta extraer referencia del nombre del producto."""
    words = nombre.split()
    for word in reversed(words):
        if any(c.isdigit() for c in word) and any(c.isalpha() for c in word) and len(word) > 4:
            return word
    return "—"


def _login(session: requests.Session, usuario: str, clave: str) -> bool:
    """Realiza el login en Gocisa."""
    try:
        # Cargar login para obtener cookies
        r = session.get(f"{BASE_URL}/es/inicio-sesion", headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        # Buscar token de formulario si existe
        token_el = soup.select_one("input[name='token']")
        token = token_el["value"] if token_el else ""

        login_data = {
            "email":        usuario,
            "passwd":       clave,
            "SubmitLogin":  "",
            "token":        token,
            "back":         "my-account",
        }
        r = session.post(
            f"{BASE_URL}/es/inicio-sesion",
            data=login_data,
            headers={**HEADERS, "Referer": f"{BASE_URL}/es/inicio-sesion"},
            timeout=20,
            allow_redirects=True,
        )
        return "logout" in r.text.lower() or "mi-cuenta" in r.url
    except Exception:
        return False


def _extract_page_products(html: str) -> list[dict]:
    """Extrae productos del HTML de una página de Gocisa."""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("li.ajax_block_product")
    products = []

    for item in items:
        name_el = item.select_one('h5[itemprop="name"] a.product-name')
        price_el = item.select_one(".right-block .price.product-price")
        img_el = item.select_one("a.product_img_link img")

        if not name_el or not price_el:
            continue

        nombre = name_el.get_text(strip=True)
        precio_raw = price_el.get_text(strip=True)
        href = name_el.get("href", "")
        if href and not href.startswith("http"):
            href = BASE_URL + href

        img_src = img_el.get("src", "") if img_el else ""
        if img_src and not img_src.startswith("http"):
            img_src = BASE_URL + img_src

        products.append({
            "nombre":     nombre,
            "precio_raw": precio_raw,
            "url":        href,
            "imagen":     img_src,
        })

    return products


async def buscar_gocisa(
    usuario: str,
    clave: str,
    familia: str,
    marca: str | None = None,
    palabra: str = "",
    margen: float = 0.40,
    max_paginas: int = 2,
    headless: bool = True,  # mantenido por compatibilidad
) -> list[dict]:
    """
    Busca productos en Gocisa usando requests+BeautifulSoup.
    """
    familia_low = familia.lower().strip()
    cat_id = CATEGORIAS.get(familia_low)

    marca_low = marca.lower().strip() if marca else None
    fab_slug = FABRICANTES.get(marca_low) if marca_low else None

    session = requests.Session()
    session.headers.update(HEADERS)

    # Login
    _login(session, usuario, clave)

    # Construir URL base
    if cat_id:
        url_base = f"{BASE_URL}/es/{cat_id}"
        if fab_slug:
            url_base += f"?q=fabricante_{fab_slug}"
    else:
        query = " ".join(filter(None, [familia, marca, palabra]))
        url_base = f"{BASE_URL}/es/buscar?controller=search&search_query={query}"

    # Scraping por páginas
    todos_productos = []

    for pagina in range(1, max_paginas + 1):
        if pagina == 1:
            url = url_base
        elif "?" in url_base:
            url = f"{url_base}&p={pagina}"
        else:
            url = f"{url_base}?p={pagina}"

        try:
            r = session.get(url, timeout=20, allow_redirects=True)
            productos_pagina = _extract_page_products(r.text)
        except Exception:
            break

        if not productos_pagina:
            break

        todos_productos.extend(productos_pagina)

        # Verificar si hay siguiente página
        soup = BeautifulSoup(r.text, "html.parser")
        next_btn = soup.select_one("li.pagination_next:not(.disabled)")
        if not next_btn:
            break

    # Calcular precios con margen
    resultados = []
    for p in todos_productos:
        coste = _parse_precio(p["precio_raw"])
        if coste is None:
            continue
        pvp = round(coste / (1 - margen), 2)
        beneficio = round(pvp - coste, 2)
        ref = _extract_ref(p["nombre"])
        resultados.append({
            "Referencia": ref,
            "Nombre":     p["nombre"],
            "Coste €":    coste,
            "PVP €":      pvp,
            "Beneficio €": beneficio,
            "URL":        p["url"],
            "Imagen":     p["imagen"],
            "Fuente":     "Gocisa",
        })

    return sorted(resultados, key=lambda x: x["Beneficio €"], reverse=True)


# ── Test directo ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    async def main():
        resultados = await buscar_gocisa(
            usuario="luis@decoyba.com",
            clave="DC151618",
            familia="hornos",
            marca="balay",
            margen=0.40,
            max_paginas=1,
        )
        print(f"\n✅ {len(resultados)} productos encontrados en Gocisa\n")
        for r in resultados[:10]:
            print(f"  {r['Referencia']:15} | {r['Nombre'][:45]:45} | {r['Coste €']:.2f}€")
    asyncio.run(main())
