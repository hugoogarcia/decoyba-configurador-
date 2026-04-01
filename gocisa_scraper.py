"""
gocisa_scraper.py — Scraper para catálogo Gocisa
Selectores verificados en sesión real (Decoyba)

Selectores confirmados:
  - Login              : input#email, input#passwd, button#SubmitLogin
  - Selector Neto/IVA  : input#b2bfee_mode_1 (antes de IVA)
  - Contenedor producto: li.ajax_block_product
  - Nombre             : h5[itemprop="name"] a.product-name
  - Precio Neto        : .right-block .price.product-price
  - Paginación         : &p={PAGE} en URL /buscar
"""

from __future__ import annotations
from playwright.async_api import async_playwright
import re, asyncio

# ── Mapeo de categorías Gocisa ───────────────────────────────────────────────
CATEGORIAS = {
    "hornos":       "23470-hornos",
    "lavadoras":    "23480-lavadoras",
    "lavado":       "23480-lavadoras",
    "lavavajillas": "23490-lavavajillas",
    "microondas":   "23500-microondas",
    "frio":         "23440-frio",
    "nevera":       "23440-frio",
    "frigorifico":  "23440-frio",
    "campana":      "23400-campanas",
    "placas":       "23530-placas-induccion",
    "placa":        "23530-placas-induccion",
    "horno_compacto": "23760-horno-independiente-45-cm-alto",
}

# ── Mapeo de fabricantes Gocisa (fragmento URL) ──────────────────────────────
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

def _parse_precio(precio_raw: str) -> float | None:
    """Convierte '62,99 € antes de IVA' → 62.99"""
    if not precio_raw:
        return None
    try:
        # Limpieza agresiva: dejar solo números y comas/puntos
        # Eliminamos "antes de IVA", "€", espacios, etc.
        limpio = (precio_raw
                  .replace("antes de IVA", "")
                  .replace("IVA incl.", "")
                  .replace("IVA incl", "")
                  .replace("€", "")
                  .replace(".", "")
                  .replace(",", ".")
                  .strip())
        # Quedarnos solo con la parte numérica por si queda basura
        match = re.search(r"(\d+\.\d+|\d+)", limpio)
        if match:
            return float(match.group(1))
        return None
    except Exception:
        return None

def _extract_ref(nombre: str) -> str:
    """Intenta extraer una referencia (ej: TR62BL, HEZ394301) del nombre."""
    # Buscamos palabras que contengan letras y números, usualmente al final
    words = nombre.split()
    for word in reversed(words):
        if any(c.isdigit() for c in word) and any(c.isalpha() for c in word) and len(word) > 4:
            return word
    return "—"

async def _extract_page_products(page) -> list[dict]:
    """Extrae productos de la página actual."""
    return await page.evaluate("""() => {
        const items = document.querySelectorAll('li.ajax_block_product');
        return Array.from(items).map(item => {
            const nameEl = item.querySelector('h5[itemprop="name"] a.product-name');
            const priceEl = item.querySelector('.right-block .price.product-price');
            const imgEl = item.querySelector('a.product_img_link img');
            const href = nameEl ? nameEl.href : '';
            return {
                nombre: nameEl ? nameEl.textContent.trim() : null,
                precio_raw: priceEl ? priceEl.textContent.trim() : null,
                url: href,
                imagen: imgEl ? imgEl.src : null
            };
        }).filter(p => p.nombre && p.precio_raw);
    }""")

async def buscar_gocisa(
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
    Busca productos en Gocisa y devuelve lista ordenada por beneficio.
    """
    familia_low = familia.lower().strip()
    cat_id = CATEGORIAS.get(familia_low)
    
    marca_low = marca.lower().strip() if marca else None
    fab_slug = FABRICANTES.get(marca_low) if marca_low else None

    # Construcción de la URL base
    if cat_id:
        url_base = f"{BASE_URL}/es/{cat_id}"
        if fab_slug:
            url_base += f"#/fabricante-{fab_slug}"
    else:
        # Fallback a búsqueda si no hay categoría mapeada
        query = " ".join(filter(None, [familia, marca, palabra]))
        url_base = f"{BASE_URL}/es/buscar?controller=search&search_query={query}"

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()

        # ── LOGIN ──────────────────────────────────────────────────────────────
        await page.goto(f"{BASE_URL}/es/inicio-sesion", wait_until="networkidle")

        # Rellenar login si no está ya autenticado
        is_logged_in = await page.query_selector("a.logout, span.account")
        if not is_logged_in:
            if await page.query_selector("input#email"):
                await page.fill("input#email", usuario)
                await page.fill("input#passwd", clave)
                await page.click("button#SubmitLogin")
                await page.wait_for_load_state("networkidle")

        # ── FORZAR MODO COMPRAR (Coste Neto para Decoyba) ─────────────────
        # Se ejecuta siempre para asegurar que estamos en el modo correcto
        try:
            await page.evaluate("""() => {
                const buyRadio = document.querySelector('input#b2bfee_mode_1');
                if (buyRadio && !buyRadio.checked) {
                    buyRadio.click();
                    buyRadio.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }""")
            await page.wait_for_timeout(1500)
        except:
            pass

        # ── SCRAPING POR PÁGINAS ───────────────────────────────────────────────
        todos_productos = []

        for pagina in range(1, max_paginas + 1):
            # En Gocisa, si hay filtros (#), la paginación a veces va en el fragmento
            current_url = url_base
            if pagina > 1:
                if "#" in current_url:
                    current_url += f"/page-{pagina}"
                elif "?" in current_url:
                    current_url += f"&p={pagina}"
                else:
                    current_url += f"#/page-{pagina}"
            
            # ── FILTRO PIROLITICO ──────────────────────────────────────────────
            if "pirolitico" in palabra.lower() or "pirolitico" in familia_low:
                if "#" in current_url:
                    current_url += "/caract-pirolitico"
                else:
                    current_url += "#/caract-pirolitico"

            await page.goto(current_url, wait_until="networkidle")
            
            # Si usamos fragmentos, Playwright puede necesitar un breve tiempo para que el JS cargue los productos
            if "#" in current_url:
                await page.wait_for_timeout(2000) # Esperar a que el AJAX cargue

            productos_pagina = await _extract_page_products(page)

            if not productos_pagina:
                break

            todos_productos.extend(productos_pagina)

            # Comprobar si hay más páginas (selector de paginación)
            next_page = await page.query_selector("li.pagination_next:not(.disabled)")
            if not next_page:
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
        ref       = _extract_ref(p["nombre"])
        
        resultados.append({
            "Referencia":           ref,
            "Nombre":               p["nombre"],
            "Coste €":              coste,
            "PVP €":                pvp,
            "Beneficio €":          beneficio,
            "URL":                  p["url"],
            "Imagen":               p["imagen"],
            "Fuente":               "Gocisa"
        })

    # Ordenar de mayor beneficio a menor
    return sorted(resultados, key=lambda x: x["Beneficio €"], reverse=True)

# ── Ejecución directa para testing ─────────────────────────────────────────────
if __name__ == "__main__":
    async def main():
        resultados = await buscar_gocisa(
            usuario="luis@decoyba.com",
            clave="DC151618",
            familia="hornos",
            marca="balay",
            margen=0.40,
            max_paginas=1,
            headless=True,
        )
        print(f"\n✅ {len(resultados)} productos encontrados en Gocisa\n")
        for r in resultados[:10]:
            print(f"  {r['Referencia']:15} | {r['Nombre'][:45]:45} | Coste: {r['Coste €']:>8.2f}€ | PVP 40%: {r[list(r.keys())[3]]:>8.2f}€ | Beneficio: {r['Beneficio €']:>7.2f}€")

    asyncio.run(main())
