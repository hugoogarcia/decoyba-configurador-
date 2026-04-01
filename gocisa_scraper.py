"""
gocisa_scraper.py — Scraper para catálogo Gocisa v2
Usa el endpoint AJAX de filtrado avanzado (blocklayered-ajax.php)
con extracción dinámica de IDs de filtros desde la página.

Estrategia:
1. Login con requests
2. Cargar la página de categoría y extraer los IDs de filtros (fabricante, capacidad, etc.)
3. Llamar al endpoint AJAX con los filtros correctos
4. Parsear el HTML devuelto por AJAX con BeautifulSoup
"""

from __future__ import annotations
import re
import requests
from bs4 import BeautifulSoup

# ── Categorías Gocisa (id numérico, slug) ─────────────────────────────────────
CATEGORIAS = {
    "hornos":         (23470, "23470-hornos"),
    "horno":          (23470, "23470-hornos"),
    "lavadoras":      (23480, "23480-lavadoras"),
    "lavadora":       (23480, "23480-lavadoras"),
    "lavado":         (23480, "23480-lavadoras"),
    "lavavajillas":   (23490, "23490-lavavajillas"),
    "microondas":     (23500, "23500-microondas"),
    "microonda":      (23500, "23500-microondas"),
    "frio":           (23440, "23440-frio"),
    "nevera":         (23440, "23440-frio"),
    "frigorifico":    (23440, "23440-frio"),
    "congelador":     (23440, "23440-frio"),
    "campana":        (23400, "23400-campanas"),
    "campanas":       (23400, "23400-campanas"),
    "placas":         (23530, "23530-placas-induccion"),
    "placa":          (23530, "23530-placas-induccion"),
    "horno_compacto": (23760, "23760-horno-independiente-45-cm-alto"),
    "secadora":       (23485, "23485-secadoras"),
    "secadoras":      (23485, "23485-secadoras"),
}

# ── Fabricantes conocidos (nombre → trozo de label a buscar en la página) ──────
FABRICANTES = {
    "aeg":        "AEG",
    "balay":      "BALAY",
    "beko":       "BEKO",
    "bosch":      "BOSCH",
    "candy":      "CANDY",
    "cata":       "CATA",
    "edesa":      "EDESA",
    "electrolux": "ELECTROLUX",
    "elica":      "ELICA",
    "hisense":    "HISENSE",
    "lg":         "LG",
    "neff":       "NEFF",
    "samsung":    "SAMSUNG",
    "siemens":    "SIEMENS",
    "smeg":       "SMEG",
    "teka":       "TEKA",
    "whirlpool":  "WHIRLPOOL",
}

BASE_URL = "http://grupo.gocisa.es"
AJAX_URL = f"{BASE_URL}/modules/blocklayered/blocklayered-ajax.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}


def _parse_precio(precio_raw: str) -> float | None:
    """Convierte '62,99 €' o '304,89 € IVA incl.' → float sin IVA (precio neto)"""
    if not precio_raw:
        return None
    try:
        # Eliminamos texto IVA
        limpio = re.sub(r'IVA.*', '', precio_raw, flags=re.IGNORECASE)
        limpio = limpio.replace("€", "").replace(".", "").replace(",", ".").strip()
        match = re.search(r"(\d+\.\d+|\d+)", limpio)
        if match:
            precio_con_iva = float(match.group(1))
            # Los precios de Gocisa llevan IVA incluido (21%) → precio neto
            return round(precio_con_iva / 1.21, 2)
        return None
    except Exception:
        return None


def _extract_ref(nombre: str) -> str:
    """Extrae referencia del nombre del producto (suele ser la segunda palabra)."""
    # Los productos de Gocisa se nombran "02LAVADORA BALAY 3TS273BA..."
    # La referencia suele ser la segunda palabra que tiene números
    words = nombre.split()
    for word in words:
        if any(c.isdigit() for c in word) and any(c.isalpha() for c in word) and len(word) > 4:
            return word.upper()
    return "—"


def _login(session: requests.Session, usuario: str, clave: str) -> bool:
    """Realiza el login en Gocisa."""
    try:
        r = session.get(f"{BASE_URL}/es/inicio-sesion", headers=HEADERS, timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")
        
        token_el = soup.select_one("input[name='token']")
        token = token_el["value"] if token_el else ""
        
        login_data = {
            "email":       usuario,
            "passwd":      clave,
            "SubmitLogin": "",
            "token":       token,
            "back":        "my-account",
        }
        r = session.post(
            f"{BASE_URL}/es/inicio-sesion",
            data=login_data,
            headers={**HEADERS, "Referer": f"{BASE_URL}/es/inicio-sesion"},
            timeout=20,
            allow_redirects=True,
        )
        return "logout" in r.text.lower() or "mi-cuenta" in r.url or "account" in r.url
    except Exception:
        return False


def _extract_filter_ids(soup: BeautifulSoup, brand_label: str | None, capacidad_kg: int | None) -> dict:
    """
    Extrae dinámicamente los IDs de los filtros de la página de categoría.
    Busca checkboxes de fabricante y capacidad.
    Devuelve un dict con los params para el AJAX.
    """
    params = {}
    
    # Buscar fabricante en los checkboxes de la sidebar
    if brand_label:
        # Buscar todos los links o checkboxes de fabricante
        for li in soup.select("div#layered_manufacturer_block_left li, div.layered_manufacturer li"):
            text = li.get_text(strip=True).upper()
            if brand_label.upper() in text:
                a = li.select_one("a")
                if a:
                    href = a.get("href", "")
                    # Extraer el ID del fabricante del onclick o del href
                    m = re.search(r"layered_manufacturer_(\d+)", href)
                    if not m:
                        m = re.search(r"'manufacturer'[^,]*,\s*'?(\d+)", href)
                    if m:
                        fab_id = m.group(1)
                        params[f"layered_manufacturer_{fab_id}"] = fab_id
                        break
                # Buscar en el input checkbox
                checkbox = li.select_one("input[type='checkbox']")
                if checkbox:
                    name = checkbox.get("name", "")
                    value = checkbox.get("value", "")
                    if name and value:
                        params[name] = value
                        break

    # Buscar capacidad en kg
    if capacidad_kg:
        target_label = f"CAPACIDAD {capacidad_kg} KG"
        for li in soup.select("div#layered_id_feature li, div.layered_id_feature_block_left li"):
            text = li.get_text(strip=True).upper()
            if target_label in text or f"{capacidad_kg} KG" in text:
                checkbox = li.select_one("input[type='checkbox']")
                if checkbox:
                    name = checkbox.get("name", "")
                    value = checkbox.get("value", "")
                    if name and value:
                        params[name] = value
                        break
                a = li.select_one("a")
                if a:
                    href = a.get("href", "")
                    m = re.search(r"layered_id_feature_(\d+)=(\d+_\d+)", href)
                    if m:
                        params[f"layered_id_feature_{m.group(1)}"] = m.group(2)
                        break

    return params


def _extract_products_from_html(html: str) -> list[dict]:
    """Extrae productos del HTML de listado de Gocisa (normal o AJAX)."""
    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("li.ajax_block_product, article.product-miniature")
    products = []

    for item in items:
        # Nombre
        name_el = (
            item.select_one('h5[itemprop="name"] a.product-name') or
            item.select_one("a.product-name") or
            item.select_one(".product-title a")
        )
        if not name_el:
            continue
        nombre = name_el.get_text(strip=True)

        # Limpiamos prefijos numéricos tipo "02LAVADORA" → "LAVADORA"
        nombre = re.sub(r"^\d{2}", "", nombre).strip()

        # Precio
        price_el = (
            item.select_one(".right-block .price.product-price") or
            item.select_one("span.price") or
            item.select_one(".product-price-and-shipping .price")
        )
        precio_raw = price_el.get_text(strip=True) if price_el else ""

        # URL
        href = name_el.get("href", "")
        if href and not href.startswith("http"):
            href = BASE_URL + href

        # Imagen
        img_el = (
            item.select_one("a.product_img_link img") or
            item.select_one(".product-image img")
        )
        img_src = ""
        if img_el:
            img_src = img_el.get("src", "") or img_el.get("data-src", "")
            if img_src and not img_src.startswith("http"):
                img_src = BASE_URL + img_src

        # Descripción corta (características rápidas debajo del nombre)
        desc_el = item.select_one(".product-desc, .product-description-short, .short-desc")
        if desc_el:
            descripcion = desc_el.get_text(" · ", strip=True)
        else:
            # Intentar coger el texto de características: "Blanco, 1.200 rpm, 7 Kg, A"
            desc_texts = item.select(".right-block p:not(.price), .product-info p")
            descripcion = " · ".join([d.get_text(strip=True) for d in desc_texts if d.get_text(strip=True)])

        if not nombre or not precio_raw:
            continue

        products.append({
            "nombre":      nombre,
            "precio_raw":  precio_raw,
            "url":         href,
            "imagen":      img_src,
            "descripcion": descripcion,
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
    headless: bool = True,
) -> list[dict]:
    """
    Busca productos en Gocisa usando AJAX para filtrado preciso.
    Extrae dinámicamente los IDs de filtros de la página antes de hacer la llamada AJAX.
    """
    familia_low = familia.lower().strip()
    cat_info = CATEGORIAS.get(familia_low)

    if not cat_info:
        # Fallback a búsqueda de texto libre
        cat_id = None
        cat_slug = None
    else:
        cat_id, cat_slug = cat_info

    marca_low = marca.lower().strip() if marca else None
    brand_label = FABRICANTES.get(marca_low) if marca_low else None

    # Detectar capacidad en kg de la palabra clave (ej: "7kg", "7 kg")
    capacidad_kg = None
    if palabra:
        m = re.search(r"(\d+)\s*kg", palabra.lower())
        if m:
            capacidad_kg = int(m.group(1))

    session = requests.Session()
    session.headers.update(HEADERS)

    # Login
    _login(session, usuario, clave)

    todos_productos = []

    if cat_id:
        # ── Cargar la página de categoría para extraer IDs de filtros ──────────
        cat_url = f"{BASE_URL}/es/{cat_slug}"
        try:
            r = session.get(cat_url, headers=HEADERS, timeout=20)
            cat_soup = BeautifulSoup(r.text, "html.parser")
        except Exception:
            cat_soup = BeautifulSoup("", "html.parser")

        # Extraer IDs dinámicos de filtros
        filter_params = _extract_filter_ids(cat_soup, brand_label, capacidad_kg)

        # ── Params base del AJAX ──────────────────────────────────────────────
        ajax_base = {
            "id_category_layered": cat_id,
            "orderby":   "price",
            "orderway":  "asc",
            "n":         "32",  # productos por página
        }
        if filter_params:
            ajax_base.update(filter_params)

        # Si hay texto adicional pero no es solo kg, añadirlo para filtrar después en Python
        texto_filtro = ""
        if palabra:
            # Eliminamos "Xkg" ya que eso lo manejamos con AJAX
            texto_filtro = re.sub(r"\d+\s*kg", "", palabra, flags=re.IGNORECASE).strip()

        for pagina in range(1, max_paginas + 1):
            params = {**ajax_base, "p": pagina}
            try:
                r = session.get(
                    AJAX_URL, params=params,
                    headers={**HEADERS, "Referer": cat_url},
                    timeout=25,
                )
                # La respuesta puede ser JSON con campo "productList" o HTML directo
                if r.headers.get("Content-Type", "").startswith("application/json"):
                    data = r.json()
                    html_content = data.get("productList", "") or data.get("products", "")
                else:
                    html_content = r.text

                productos_pagina = _extract_products_from_html(html_content)
            except Exception:
                break

            if not productos_pagina:
                break

            todos_productos.extend(productos_pagina)

            # Comprobar si hay siguiente página
            soup_page = BeautifulSoup(html_content, "html.parser")
            if not soup_page.select_one("li.pagination_next:not(.disabled)"):
                break

    else:
        # ── Fallback: búsqueda de texto libre ─────────────────────────────────
        query = " ".join(filter(None, [familia, marca, palabra]))
        search_url = f"{BASE_URL}/es/buscar?controller=search&search_query={query}"

        for pagina in range(1, max_paginas + 1):
            url = search_url if pagina == 1 else f"{search_url}&p={pagina}"
            try:
                r = session.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
                productos_pagina = _extract_products_from_html(r.text)
            except Exception:
                break

            if not productos_pagina:
                break
            todos_productos.extend(productos_pagina)

            soup_p = BeautifulSoup(r.text, "html.parser")
            if not soup_p.select_one("li.pagination_next:not(.disabled)"):
                break

    # ── Filtro adicional por texto libre (capacidad, acabado, etc.) ────────────
    if palabra and todos_productos:
        # Filtrar por palabras clave que no se cubrieron con AJAX
        palabras_filtro = [w for w in palabra.lower().split()
                          if len(w) > 2 and not re.match(r'\d+kg?', w)]
        if palabras_filtro:
            filtrados = []
            for p in todos_productos:
                texto_prod = (p["nombre"] + " " + p["descripcion"]).lower()
                if any(pal in texto_prod for pal in palabras_filtro):
                    filtrados.append(p)
            # Solo aplicar el filtro si no vacía demasiado los resultados
            if len(filtrados) >= max(1, len(todos_productos) // 4):
                todos_productos = filtrados

    # ── Calcular precios con margen ────────────────────────────────────────────
    resultados = []
    seen = set()
    for p in todos_productos:
        coste = _parse_precio(p["precio_raw"])
        if coste is None or coste <= 0:
            continue
        key = p["nombre"][:30].lower()
        if key in seen:
            continue
        seen.add(key)

        pvp = round(coste / (1 - margen), 2)
        beneficio = round(pvp - coste, 2)
        ref = _extract_ref(p["nombre"])

        resultados.append({
            "Referencia":  ref,
            "Nombre":      p["nombre"],
            "Descripcion": p["descripcion"],
            "Coste €":     coste,
            "PVP €":       pvp,
            "Beneficio €": beneficio,
            "URL":         p["url"],
            "Imagen":      p["imagen"],
            "Fuente":      "Gocisa",
        })

    return sorted(resultados, key=lambda x: x["Beneficio €"], reverse=True)


# ── Test directo ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    async def main():
        resultados = await buscar_gocisa(
            usuario="luis@decoyba.com",
            clave="DC151618",
            familia="lavadora",
            marca="balay",
            palabra="7kg",
            margen=0.40,
            max_paginas=1,
        )
        print(f"\n✅ {len(resultados)} productos encontrados en Gocisa\n")
        for r in resultados[:10]:
            print(f"  {r['Referencia']:15} | {r['Nombre'][:40]:40} | {r['Coste €']:.2f}€ neto | {r['Descripcion'][:50]}")
    asyncio.run(main())
