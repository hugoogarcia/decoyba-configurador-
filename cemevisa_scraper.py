"""
cemevisa_scraper.py — Scraper para catálogo Cemevisa
Selectores verificados directamente en el DOM (sesión de Decoyba)

Selectores confirmados:
  - Contenedor producto : tr.bloque
  - Nombre              : tr.bloque td.tres-col a.tt p.titular
  - Precio Neto         : tr.bloque td.precioneto
  - Referencia          : regex en href del enlace  /p-([^/]+)/
  - Paginación          : offset +20 en URL  /f-{FAMILIA}-0-{OFFSET}/
"""

from __future__ import annotations
from playwright.async_api import async_playwright
import re, asyncio

# ── Códigos de familia (extraídos del JS de Cemevisa) ──────────────────────────
FAMILIAS = {
    "hornos":       "000009",
    "horno":        "000009",
    "frio":         "frio",
    "nevera":       "frio",
    "frigorifico":  "frio",
    "lavadora":     "000002",
    "lavado":       "000002",
    "lavavajillas": "000003",
    "placas":       "placas",
    "placa":        "placas",
    "campana":      "000007",
    "microondas":   "001425",
    "microonda":    "001425",
    "secadora":     "000002",   # agrupada con lavado
    "horno_compacto": "000009",  # mismo que hornos pero filtraremos por palabra
}

# ── Códigos de marca ────────────────────────────────────────────────────────────
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


def _build_url(familia_code: str, marca_code: str = "", palabra: str = "", offset: int = 0) -> str:
    """Construye la URL de catálogo filtrada de Cemevisa."""
    # Patrón: /es/todo/todo/f-{FAMILIA}-0-{OFFSET}/c-{PALABRA}------{MARCA}---/
    palabra_url = palabra.strip().replace(" ", "-").lower() if palabra else ""
    return f"{BASE_URL}/es/todo/todo/f-{familia_code}-0-{offset}/c-{palabra_url}------{marca_code}---/"


def _parse_precio(precio_raw: str) -> float | None:
    """Convierte '306,00€' → 306.0"""
    try:
        limpio = precio_raw.replace("€", "").replace(".", "").replace(",", ".").strip()
        return float(limpio)
    except Exception:
        return None


async def _extract_page_products(page) -> list[dict]:
    """Extrae productos de la página actual usando los selectores verificados."""
    return await page.evaluate("""() => {
        const rows = document.querySelectorAll('tr.bloque');
        return Array.from(rows).map(row => {
            const enlace  = row.querySelector('td.tres-col a.tt');
            const titular = row.querySelector('td.tres-col a.tt p.titular');
            const precioEl = row.querySelector('td.precioneto');
            const imgEl    = row.querySelector('a.tt div img');
            const href     = enlace ? enlace.href : '';
            const refMatch = href.match(/\\/p-([^\\/]+)\\//);
            return {
                nombre    : titular ? titular.textContent.trim() : (enlace ? enlace.textContent.replace(/\\s+/g,' ').trim() : null),
                referencia: refMatch ? refMatch[1] : null,
                precio_raw: precioEl ? precioEl.textContent.trim() : null,
                url       : href,
                imagen    : imgEl ? imgEl.src : null
            };
        }).filter(p => p.nombre && p.precio_raw);
    }""")


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
    Busca productos en Cemevisa y devuelve lista ordenada por beneficio.

    Args:
        usuario     : Cliente Cemevisa (ej: '13323')
        clave       : Contraseña Cemevisa
        familia     : Tipo de producto en español (ej: 'hornos', 'nevera', 'lavadora')
        marca       : Marca en español (ej: 'balay', 'bosch') o None para todas
        palabra     : Texto libre adicional (ej: 'pirolítico', 'bajo consumo')
        margen      : Margen sobre coste en decimal (0.40 = 40%)
        max_paginas : Número máximo de páginas a escanear (20 productos/página)
        headless    : False para ver el navegador en pantalla (útil para debug)

    Returns:
        Lista de dicts ordenada de mayor a menor beneficio.
    """
    familia_lower = familia.lower().strip()
    familia_code  = FAMILIAS.get(familia_lower, "")
    if not familia_code:
        raise ValueError(f"Familia '{familia}' no reconocida. Opciones: {list(FAMILIAS.keys())}")

    marca_code = ""
    if marca:
        marca_code = MARCAS.get(marca.lower().strip(), "")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        # ── LOGIN ──────────────────────────────────────────────────────────────
        await page.goto(BASE_URL, wait_until="networkidle")

        # Rellenar login si no está ya autenticado
        is_logged_in = await page.query_selector("a[href*='/logout/']")
        if not is_logged_in:
            if await page.query_selector("#Tusuario"):
                await page.fill("#Tusuario", usuario)
                await page.fill("#Tclave", clave)
                await page.click("input[type=submit], button[type=submit]")
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(3000)
        
        # ── ASEGURAR MODO NETO ─────────────────────────────────────────────
        # Si la URL contiene /tienda/, estamos en modo PVPR (caro).
        # Aunque _build_url no lo pone, si navegamos por error, esto lo arregla.
        if "/tienda/" in page.url:
            await page.goto(page.url.replace("/tienda/", "/"), wait_until="networkidle")

        # ── SCRAPING POR PÁGINAS ───────────────────────────────────────────────
        todos_productos = []

        for pagina in range(max_paginas):
            offset = pagina * 20
            # En Cemevisa es mejor buscar por marca/familia y filtrar compacto en Python
            # para evitar que el buscador interno (muy estricto) devuelva 0.
            palabra_busqueda = palabra 
            
            url = _build_url(familia_code, marca_code, palabra_busqueda, offset)
            await page.goto(url, wait_until="load") # 'load' es más rápido y seguro si hay mucha red
            await page.wait_for_timeout(1000)

            productos_pagina = await _extract_page_products(page)

            if not productos_pagina:
                break   # Sin más productos → fin

            todos_productos.extend(productos_pagina)

            # Comprobar si hay más páginas
            total_text = await page.query_selector(".pagination p")
            if total_text:
                text = await total_text.text_content()
                # "Mostrando página X de Y (Z artículos)"
                match = re.search(r"página (\d+) de (\d+)", text or "")
                if match:
                    pag_actual = int(match.group(1))
                    pag_total  = int(match.group(2))
                    if pag_actual >= pag_total:
                        break

        await browser.close()

    # ── CALCULAR PRECIOS CON MARGEN ────────────────────────────────────────────
    resultados = []
    for p in todos_productos:
        coste = _parse_precio(p["precio_raw"])
        if coste is None:
            continue
        pvp       = round(coste / (1 - margen), 2)
        beneficio = round(pvp - coste, 2)
        resultados.append({
            "Referencia":           p["referencia"] or "—",
            "Nombre":               p["nombre"],
            "Coste €":              coste,
            "PVP €":                pvp,
            "Beneficio €":          beneficio,
            "URL":                  p["url"],
            "Imagen":               p["imagen"],
            "Fuente":               "Cemevisa",
        })

    # ── FILTRO POST-SEARCH PARA COMPACTOS ──────────────────────────────────────
    if familia_lower == "horno_compacto":
        # Filtrar por palabras clave si no vinieron ya filtrados
        resultados = [r for r in resultados if "45" in r["Nombre"] or "COMPACT" in r["Nombre"].upper()]

    # Ordenar de mayor beneficio a menor
    return sorted(resultados, key=lambda x: x["Beneficio €"], reverse=True)


# ── Ejecución directa para testing ─────────────────────────────────────────────
if __name__ == "__main__":
    import json

    async def main():
        resultados = await buscar_cemevisa(
            usuario="13323",
            clave="2h74",
            familia="hornos",
            marca="balay",
            margen=0.40,
            max_paginas=2,
            headless=True,
        )
        print(f"\n✅ {len(resultados)} productos encontrados\n")
        for r in resultados[:10]:
            print(f"  {r['Referencia']:15} | {r['Nombre'][:45]:45} | Coste: {r['Coste €']:>8.2f}€ | PVP 40%: {r['PVP 40%']:>8.2f}€ | Beneficio: {r['Beneficio €']:>7.2f}€")

    asyncio.run(main())
