"""
cemevisa_scraper.py — Scraper para catálogo Cemevisa
Versión Requests+BeautifulSoup (compatible con Streamlit Cloud, sin Playwright)
"""

from __future__ import annotations
import re
import requests
from bs4 import BeautifulSoup

# ── Códigos de familia ─────────────────────────────────────────────────────────
FAMILIAS = {
    "hornos":         "000009",
    "horno":          "000009",
    "frio":           "frio",
    "nevera":         "frio",
    "frigorifico":    "frio",
    "lavadora":       "000002",
    "lavado":         "000002",
    "lavavajillas":   "000003",
    "placas":         "placas",
    "placa":          "placas",
    "campana":        "000007",
    "microondas":     "001425",
    "microonda":      "001425",
    "secadora":       "000002",
    "horno_compacto": "000009",
}

# ── Códigos de marca ───────────────────────────────────────────────────────────
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
}

BASE_URL = "https://www.cemevisa.com"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}


def _build_url(familia_code: str, marca_code: str = "", palabra: str = "", offset: int = 0) -> str:
    palabra_url = palabra.strip().replace(" ", "-").lower() if palabra else ""
    return f"{BASE_URL}/es/todo/todo/f-{familia_code}-0-{offset}/c-{palabra_url}------{marca_code}---/"


def _parse_precio(precio_raw: str) -> float | None:
    try:
        limpio = precio_raw.replace("€", "").replace(".", "").replace(",", ".").strip()
        return float(limpio)
    except Exception:
        return None


def _login(session: requests.Session, usuario: str, clave: str) -> bool:
    """Realiza el login en Cemevisa y devuelve True si fue exitoso."""
    try:
        # Cargar la página principal para obtener cookies de sesión
        r = session.get(BASE_URL, headers=HEADERS, timeout=20)
        # Enviar formulario de login
        login_data = {
            "Tusuario": usuario,
            "Tclave": clave,
            "accion": "login",
        }
        r = session.post(f"{BASE_URL}/es/login/", data=login_data, headers=HEADERS, timeout=20)
        # Verificar que estamos autenticados buscando el enlace de logout
        return "logout" in r.text.lower() or usuario in r.text
    except Exception:
        return False


def _extract_page_products(html: str) -> list[dict]:
    """Extrae productos del HTML de una página de Cemevisa."""
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("tr.bloque")
    products = []
    for row in rows:
        enlace = row.select_one("td.tres-col a.tt")
        titular = row.select_one("td.tres-col a.tt p.titular")
        precio_el = row.select_one("td.precioneto")
        img_el = row.select_one("a.tt div img")

        if not enlace or not precio_el:
            continue

        href = enlace.get("href", "")
        if not href.startswith("http"):
            href = BASE_URL + href

        ref_match = re.search(r"/p-([^/]+)/", href)
        nombre = titular.get_text(strip=True) if titular else enlace.get_text(" ", strip=True)
        precio_raw = precio_el.get_text(strip=True)

        if not nombre or not precio_raw:
            continue

        img_src = img_el.get("src", "") if img_el else ""
        if img_src and not img_src.startswith("http"):
            img_src = BASE_URL + img_src

        products.append({
            "nombre":     nombre,
            "referencia": ref_match.group(1) if ref_match else "—",
            "precio_raw": precio_raw,
            "url":        href,
            "imagen":     img_src,
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
    headless: bool = True,  # mantenido por compatibilidad, ya no se usa
) -> list[dict]:
    """
    Busca productos en Cemevisa usando requests+BeautifulSoup.
    """
    familia_lower = familia.lower().strip()
    familia_code = FAMILIAS.get(familia_lower, "")
    if not familia_code:
        raise ValueError(f"Familia '{familia}' no reconocida. Opciones: {list(FAMILIAS.keys())}")

    marca_code = ""
    if marca:
        marca_code = MARCAS.get(marca.lower().strip(), "")

    session = requests.Session()
    session.headers.update(HEADERS)

    # Login
    _login(session, usuario, clave)

    # Scraping por páginas
    todos_productos = []

    for pagina in range(max_paginas):
        offset = pagina * 20
        url = _build_url(familia_code, marca_code, palabra, offset)

        try:
            r = session.get(url, timeout=20)
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
            "Referencia": p["referencia"],
            "Nombre":     p["nombre"],
            "Coste €":    coste,
            "PVP €":      pvp,
            "Beneficio €": beneficio,
            "URL":        p["url"],
            "Imagen":     p["imagen"],
            "Fuente":     "Cemevisa",
        })

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
            margen=0.40,
            max_paginas=2,
        )
        print(f"\n✅ {len(resultados)} productos encontrados\n")
        for r in resultados[:10]:
            print(f"  {r['Referencia']:15} | {r['Nombre'][:45]:45} | {r['Coste €']:.2f}€")
    asyncio.run(main())
