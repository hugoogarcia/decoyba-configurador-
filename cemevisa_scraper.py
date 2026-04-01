"""
cemevisa_scraper.py — Scraper para catálogo Cemevisa v3
URLs verificadas directamente del DOM (todas las categorías, marcas y subfamilias).

Estructura de URL: /es/{categoria}/{subcategoria}/f-{FAMILIA}-{SUBFAMILIA}/
Filtro por marca: añadir /c------{MARCA_CODE}-----/ al final
Filtro por texto: añadir /c-{TEXTO}------{MARCA_CODE}---/ al final
Paginación: f-{FAMILIA}-{SUBFAMILIA}-{OFFSET}/ (offset += 20 por página)
"""

from __future__ import annotations
import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.cemevisa.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}

# ── URLs de categorías verificadas ─────────────────────────────────────────────
# Formato: "familia" -> lista de (url_path, subfamilia_code)
# Se prueban en orden y se usan todas las que devuelvan productos
CATEGORIAS_URL = {
    "hornos": [
        ("/es/hornos/hornos-alto-60-cm/f-000009-0009i/", "hornos-libres-60cm"),
        ("/es/hornos/hornos-alto-45-cm/f-000009-0009i45/", "hornos-45cm"),
        ("/es/hornos/hornos-polivalentes-alto-60-cm/f-000009-0009p/", "hornos-polivalentes"),
    ],
    "horno": [
        ("/es/hornos/hornos-alto-60-cm/f-000009-0009i/", "hornos-60cm"),
        ("/es/hornos/hornos-polivalentes-alto-60-cm/f-000009-0009p/", "hornos-polivalentes"),
    ],
    "horno_compacto": [
        ("/es/hornos/hornos-alto-45-cm/f-000009-0009i45/", "hornos-45cm"),
    ],
    "frio": [
        ("/es/frio/combi/f-frio-0000c/", "frio-combi"),
        ("/es/frio/americanos-side-by-side/f-frio-fsideby/", "frio-sbs"),
        ("/es/frio/americanos-puerta-francesa/f-frio-fpfrances/", "frio-francesa"),
        ("/es/frio/frigorificos-2-puertas/f-frio-00002p/", "frio-2p"),
        ("/es/frio/frigorificos-1-puerta/f-frio-00001p/", "frio-1p"),
    ],
    "nevera": [
        ("/es/frio/combi/f-frio-0000c/", "frio-combi"),
        ("/es/frio/frigorificos-2-puertas/f-frio-00002p/", "frio-2p"),
    ],
    "frigorifico": [
        ("/es/frio/combi/f-frio-0000c/", "frio-combi"),
        ("/es/frio/frigorificos-2-puertas/f-frio-00002p/", "frio-2p"),
    ],
    "congelador": [
        ("/es/frio/congeladores-verticales/f-frio-0000cv/", "congeladores"),
        ("/es/frio/arcones-congeladores/f-frio-0000a/", "arcones"),
    ],
    "lavadora": [
        ("/es/lavado-y-secado/lavadoras-libre-instalacion/f-000002-0002/", "lavadoras-libres"),
        ("/es/lavado-y-secado/lavadoras-integrables/f-000002-lavaint/", "lavadoras-int"),
    ],
    "lavadoras": [
        ("/es/lavado-y-secado/lavadoras-libre-instalacion/f-000002-0002/", "lavadoras-libres"),
    ],
    "lavavajillas": [
        ("/es/lavavajillas/lavavajillas-60-cm-libre-instalacion/f-000003-000360/", "lvj-60cm"),
        ("/es/lavavajillas/lavavajillas-45-cm-libre-instalacion/f-000003-000345/", "lvj-45cm"),
        ("/es/lavavajillas/lavavajillas-60-cm-integrables/f-000003-60int/", "lvj-60cm-int"),
        ("/es/lavavajillas/lavavajillas-45-cm-integrables/f-000003-45int/", "lvj-45cm-int"),
    ],
    "placas": [
        ("/es/placas/induccion/f-placas-induc/", "placas-induccion"),
        ("/es/placas/vitroceramica/f-placas-vitro/", "placas-vitro"),
        ("/es/placas/gas/f-placas-gas/", "placas-gas"),
        ("/es/placas/mixtas/f-placas-mixta/", "placas-mixtas"),
    ],
    "placa": [
        ("/es/placas/induccion/f-placas-induc/", "placas-induccion"),
        ("/es/placas/vitroceramica/f-placas-vitro/", "placas-vitro"),
    ],
    "campana": [
        ("/es/campanas/campanas-decorativas-pared/f-000007-0007chp/", "campanas-pared"),
        ("/es/campanas/campanas-decorativas-isla/f-000007-0007chi/", "campanas-isla"),
        ("/es/campanas/campanas-extraplanas/f-000007-0007cex/", "campanas-extrapl"),
        ("/es/campanas/campanas-integradas/f-000007-0007ci/", "campanas-int"),
    ],
    "campanas": [
        ("/es/campanas/campanas-decorativas-pared/f-000007-0007chp/", "campanas-pared"),
        ("/es/campanas/campanas-extraplanas/f-000007-0007cex/", "campanas-extrapl"),
    ],
    "microondas": [
        ("/es/microondas/microondas-libre-instalacion/f-001425-libre/", "microondas-libres"),
        ("/es/microondas/microondas-integrable/f-001425-inte/", "microondas-int"),
    ],
    "microonda": [
        ("/es/microondas/microondas-libre-instalacion/f-001425-libre/", "microondas-libres"),
    ],
    "secadora": [
        ("/es/lavado-y-secado/secadora-bomba-de-calor/f-000002-secabom/", "secadoras-bomba"),
        ("/es/lavado-y-secado/lavasecadoras-libre-instalacion/f-000002-0002ls/", "lavasecadoras"),
    ],
    "secadoras": [
        ("/es/lavado-y-secado/secadora-bomba-de-calor/f-000002-secabom/", "secadoras-bomba"),
    ],
}

# ── Códigos de marca para filtrado ─────────────────────────────────────────────
MARCAS = {
    "balay":      "bsh49",
    "bosch":      "bshb2",
    "siemens":    "bshs3",
    "aeg":        "ge39",
    "electrolux": "ge08",
    "cata":       "cna38",
    "teka":       "tek11",
    "beko":       "bek01",
    "hisense":    "his01",
    "samsung":    "sam01",
    "lg":         "lg001",
    "whirlpool":  "whi01",
    "neff":       "bshn1",
    "candy":      "can01",
    "edesa":      "ede01",
    "smeg":       "sme01",
}


def _parse_precio(precio_raw: str) -> float | None:
    """Convierte '306,00€' → 306.0"""
    try:
        limpio = precio_raw.replace("€", "").replace(".", "").replace(",", ".").strip()
        return float(limpio)
    except Exception:
        return None


def _login(session: requests.Session, usuario: str, clave: str) -> bool:
    """Realiza el login en Cemevisa."""
    try:
        session.get(BASE_URL, headers=HEADERS, timeout=15)
        r = session.post(
            f"{BASE_URL}/es/usuarios/identificar/",
            data={"Tusuario": usuario, "Tclave": clave, "accion": "login"},
            headers=HEADERS, timeout=20, allow_redirects=True,
        )
        return "logout" in r.text.lower()
    except Exception:
        return False


def _build_paginated_url(base_path: str, offset: int, marca_code: str = "", palabra: str = "") -> str:
    """
    Construye URL con paginación y filtros de marca/texto.
    
    Cemevisa paginación: agrega -OFFSET al final del segmento f-xxx
    Ejemplo: /es/lavavajillas/.../f-000003-000360/  ->  /es/lavavajillas/.../f-000003-000360-20/
    Filtro marca: /c------{MARCA_CODE}-----/
    Filtro texto+marca: /c-{TEXTO}------{MARCA_CODE}---/
    """
    if offset == 0:
        paginated_path = base_path
    else:
        # Insertar offset antes del slash final del segmento f-xxx
        # /es/cat/subcat/f-FAMILIA-SUB/ -> /es/cat/subcat/f-FAMILIA-SUB-OFFSET/
        paginated_path = re.sub(r'(f-[^/]+)/([^/]*)$', lambda m: f"{m.group(1)}-{offset}/{m.group(2)}", base_path)
        if paginated_path == base_path:  # fallback si no hay segmento f-
            paginated_path = base_path.rstrip('/') + f'-{offset}/'

    filters = ""
    if palabra or marca_code:
        palabra_url = palabra.strip().replace(" ", "-").lower() if palabra else ""
        filters = f"/c-{palabra_url}------{marca_code}---/"

    return f"{BASE_URL}{paginated_path}{filters}"


def _extract_page_products(html: str) -> list[dict]:
    """Extrae productos del HTML de una página de listado de Cemevisa."""
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr.bloque")
    products = []

    for row in rows:
        enlace = row.select_one("td.tres-col a.tt")
        titular = row.select_one("td.tres-col a.tt p.titular")
        precio_el = row.select_one("td.precioneto")

        if not enlace or not precio_el:
            continue

        href = enlace.get("href", "")
        if not href.startswith("http"):
            href = BASE_URL + href

        nombre = titular.get_text(strip=True) if titular else enlace.get_text(" ", strip=True)
        precio_raw = precio_el.get_text(strip=True)

        if not nombre or not precio_raw:
            continue

        # Referencia
        ref_match = re.search(r"/p-([^/]+)/", href)
        referencia = ref_match.group(1) if ref_match else "—"

        # Imagen
        img_el = row.select_one("a.tt div img")
        img_src = ""
        if img_el:
            img_src = img_el.get("src", "") or img_el.get("data-src", "")
            if img_src and not img_src.startswith("http"):
                img_src = BASE_URL + img_src

        # Descripción / características (bullets ul.punto)
        desc_items = row.select("ul.punto li")
        descripcion = " · ".join([li.get_text(strip=True) for li in desc_items if li.get_text(strip=True)])

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
    max_paginas: int = 2,
    headless: bool = True,
) -> list[dict]:
    """
    Busca productos en Cemevisa usando requests+BeautifulSoup con URLs reales verificadas.
    """
    familia_lower = familia.lower().strip()
    cat_urls = CATEGORIAS_URL.get(familia_lower)

    if not cat_urls:
        raise ValueError(f"Familia '{familia}' no reconocida. Opciones: {list(CATEGORIAS_URL.keys())}")

    marca_code = ""
    if marca:
        marca_code = MARCAS.get(marca.lower().strip(), "")

    session = requests.Session()
    session.headers.update(HEADERS)

    # Login
    _login(session, usuario, clave)

    todos_productos = []
    seen_refs = set()

    # Iterar sobre las subcategorías relevantes
    for base_path, _ in cat_urls:
        for pagina in range(max_paginas):
            offset = pagina * 20
            url = _build_paginated_url(base_path, offset, marca_code, palabra)

            try:
                r = session.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
                if r.status_code == 404 or "404" in r.url:
                    break
                productos_pagina = _extract_page_products(r.text)
            except Exception:
                break

            if not productos_pagina:
                break

            for p in productos_pagina:
                if p["referencia"] not in seen_refs:
                    todos_productos.append(p)
                    seen_refs.add(p["referencia"])

            # Comprobar paginación
            soup = BeautifulSoup(r.text, "html.parser")
            pag_text = soup.select_one(".pagination p")
            if pag_text:
                match = re.search(r"página (\d+) de (\d+)", pag_text.get_text())
                if match and int(match.group(1)) >= int(match.group(2)):
                    break

        # Límite razonable: con la primera subcategoría que da resultados, basta
        if len(todos_productos) >= 15:
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

    return sorted(resultados, key=lambda x: x["Beneficio €"], reverse=True)


# ── Test directo ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    async def main():
        resultados = await buscar_cemevisa(
            usuario="13323",
            clave="2h74",
            familia="lavavajillas",
            marca=None,
            palabra="",
            margen=0.40,
            max_paginas=1,
        )
        print(f"\n✅ {len(resultados)} productos encontrados\n")
        for r in resultados[:8]:
            print(f"  {r['Referencia']:15} | {r['Nombre'][:45]:45} | {r['Coste €']:.2f}€")
            if r['Descripcion']:
                print(f"    📋 {r['Descripcion'][:80]}")
    asyncio.run(main())
