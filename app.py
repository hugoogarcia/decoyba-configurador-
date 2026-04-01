"""
app.py — Configurador de Producto DECOYBA (Versión Premium v3)
Mejoras: Modo Coste Real, Tarjetas Clicables y Ranking Inteligente.
"""

import streamlit as st
import asyncio
import pandas as pd
import time
import nest_asyncio
from datetime import datetime
import base64

# Necesario para que asyncio funcione dentro de Streamlit
nest_asyncio.apply()

from interpreter import interpretar
from cemevisa_scraper import buscar_cemevisa
from gocisa_scraper import buscar_gocisa

# ── Configuración de página ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="DECOYBA · Elite Dashboard",
    page_icon="logo.png",
    layout="wide",
    initial_sidebar_state="collapsed", # Más limpio
)

# ── Inicializar Estado de Sesión ────────────────────────────────────────────────
if "history" not in st.session_state:
    st.session_state.history = []

def get_base64_logo():
    try:
        with open("logo.png", "rb") as f:
            data = f.read()
            return base64.b64encode(data).decode()
    except:
        return ""

# ── CSS Corporativo DECOYBA (Light & Clean) ──────────────────────────────────
logo_b64 = get_base64_logo()
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700;800&display=swap');

    :root {{
        --brand-main: #1D1D1B; /* Oscuro corporativo principal */
        --brand-accent: #D4AF37; /* Dorado clásico corporativo (siempre elegante) */
        --bg-color: #F8F9FA;
        --card-bg: #FFFFFF;
        --border-light: #E0E0E0;
        --text-main: #333333;
        --text-muted: #666666;
        --success: #28a745;
    }}

    /* Global */
    html, body, [class*="css"] {{
        font-family: 'Open Sans', sans-serif !important;
        background-color: var(--bg-color) !important;
        color: var(--text-main) !important;
    }}
    
    .stApp {{
        background: var(--bg-color) !important;
    }}

    /* Sidebar Standard pero Limpia */
    [data-testid="stSidebar"] {{
        background-color: #f1f3f5 !important;
        border-right: 1px solid var(--border-light) !important;
        padding-top: 1rem;
    }}
    .stSlider > div > div > div > div {{
        background: var(--brand-main) !important;
    }}
    [data-testid="stWidgetLabel"] p {{
        color: var(--brand-main) !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
    }}

    /* HEADER CORPORATIVO */
    .header-lux {{
        display: flex;
        flex-direction: column;
        align-items: center;
        padding: 3rem 1rem;
        background: var(--card-bg);
        border-bottom: 2px solid var(--border-light);
        margin-bottom: 2rem;
    }}
    .logo-img {{
        width: 150px;
        margin-bottom: 1rem;
    }}
    .brand-name {{
        font-size: 2.5rem !important;
        font-weight: 800 !important;
        color: var(--brand-main);
        letter-spacing: -1px;
        margin: 0;
    }}

    /* INPUTS DE BÚSQUEDA CLAROS */
    .search-container-v2 {{
        max-width: 800px;
        margin: 0 auto;
        padding: 2rem;
        background: var(--card-bg);
        border: 1px solid var(--border-light);
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }}
    
    .stTextInput input {{
        background: #ffffff !important;
        color: var(--text-main) !important;
        height: 60px !important;
        font-size: 1.2rem !important;
        border: 2px solid var(--border-light) !important;
        border-radius: 6px !important;
        padding: 0 1rem !important;
    }}
    .stTextInput input:focus {{
        border-color: var(--brand-main) !important;
        box-shadow: none !important;
    }}
    
    .stButton button {{
        background: var(--brand-main) !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 6px !important;
        height: 55px !important;
        font-size: 1.1rem !important;
        transition: 0.2s ease !important;
        width: 100% !important;
        margin-top: 1rem;
    }}
    .stButton button:hover {{
        background: #000000 !important;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1) !important;
    }}

    /* CARDS ESTILO E-COMMERCE CLÁSICO */
    .glass-card {{
        background: var(--card-bg);
        border: 1px solid var(--border-light);
        border-radius: 8px;
        padding: 2rem;
        transition: 0.2s ease;
        position: relative;
        box-shadow: 0 2px 5px rgba(0,0,0,0.02);
    }}
    .glass-card:hover {{
        border-color: var(--brand-main);
        box-shadow: 0 8px 20px rgba(0,0,0,0.08);
    }}

    .featured-ribbon {{
        position: absolute;
        top: 20px;
        left: -35px;
        background: var(--brand-main);
        color: #ffffff;
        padding: 5px 40px;
        font-weight: 700;
        font-size: 0.8rem;
        transform: rotate(-15deg);
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }}

    .img-container {{
        background: #ffffff;
        padding: 1rem;
        height: 250px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 1rem;
    }}
    
    .price-main {{
        font-size: 3rem !important;
        font-weight: 800 !important;
        color: var(--brand-main) !important;
        margin: 0.5rem 0;
    }}
    .price-sub {{
        color: var(--text-muted);
        font-size: 0.9rem;
    }}
    
    .profit-text {{
        color: var(--success);
        font-weight: 700;
        font-size: 1.1rem;
    }}

    .btn-supplier {{
        display: inline-block;
        background: var(--brand-main);
        color: #ffffff !important;
        padding: 0.8rem 1.5rem;
        border-radius: 4px;
        font-weight: 600;
        text-align: center;
        margin-top: 1rem;
        width: 100%;
        text-decoration: none !important;
    }}
    .btn-supplier:hover {{
        background: #000000;
    }}

    h1, h2, h3, h4 {{
        color: var(--brand-main) !important;
    }}

</style>

<div class="header-lux">
    <img src="data:image/png;base64,{logo_b64}" class="logo-img">
    <h1 class="brand-name">Portal de Ventas</h1>
</div>
""" , unsafe_allow_html=True)

# ── Sidebar: Historial ────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏺 Historial de Inteligencia")
    for h in reversed(st.session_state.history[-8:]):
        if st.button(f"🔎 {h['query'][:22]}...", key=f"h_{h['timestamp']}", use_container_width=True):
            st.session_state.search_trigger = h['query']
    
    st.divider()
    margen_pct = st.slider("Margen Objetivo", 20, 60, 40, 5, format="%d%%")
    bus_sources = st.multiselect("Fuentes", ["Cemevisa", "Gocisa"], default=["Cemevisa", "Gocisa"])

# ── Search Interface ──────────────────────────────────────────────────────────
# ── Search Interface (Command Center) ─────────────────────────────────────────
st.markdown('<div class="search-container-v2">', unsafe_allow_html=True)
query_input = st.text_input("Búsqueda de productos", placeholder="Ej: lavadora bosch, horno balay, frigorífico...", label_visibility="collapsed")
buscar = st.button("BUSCAR", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

if "search_trigger" in st.session_state:
    query_input = st.session_state.pop("search_trigger")
    buscar = True

def filter_and_rank(results, params):
    """Lógica de ranking inteligente v3."""
    # 1. Filtro estricto de accesorios y repuestos
    keywords = [
        "ACCESORIO", "ACCESOR", "BANDEJA", "REPUESTO", "KIT", "SOPORTE", "PAE", "LIMPIADOR",
        "TUBO", "CESTO", "MANGUERA", "DESAGUE", "EVACUACION", "CABLE", "MOTOR", "REJILLA", 
        "FILTRO", "TAPA", "BISAGRA", "GUIAS", "GUIA", "BOMBILLA", "LAMPARA", "UNION"
    ]
    
    clean_list = []
    for r in results:
        nombre_upper = r["Nombre"].upper()
        # Rechazar si contiene palabras clave de accesorio
        if any(k in nombre_upper for k in keywords):
            continue
            
        # Rechazar si el coste es irremediablemente bajo para ser un electrodoméstico principal (<45€)
        # (Todos los productos del configurador son gama blanca: hornos, frigos, lavadoras, etc.)
        if r["Coste €"] < 45.0:
            continue
            
        clean_list.append(r)
    
    # Si la limpieza es tan agresiva que vacía la lista, devolvemos los resultados originales por si acaso
    if not clean_list: 
        clean_list = results
    
    # 2. Ranking dinámico
    if params.get("barato"):
        # Priorizar coste bajo (pero ya limpios de accesorios basura)
        return sorted(clean_list, key=lambda x: x["Coste €"])
    elif params.get("premium"):
        # Priorizar marcas top y beneficio absoluto
        top_maras = ["SIEMENS", "BOSCH", "NEFF", "AEG"]
        return sorted(clean_list, key=lambda x: (any(m in x["Nombre"].upper() for m in top_maras), x["Beneficio €"]), reverse=True)
    else:
        # Default: máximo beneficio
        return sorted(clean_list, key=lambda x: x["Beneficio €"], reverse=True)

if buscar and query_input:
    if not any(h['query'] == query_input for h in st.session_state.history):
        st.session_state.history.append({"query": query_input, "timestamp": time.time()})

    try:
        creds = {
            "cem": (st.secrets["CEM_USER"], st.secrets["CEM_PASS"]),
            "goc": (st.secrets["GOC_USER"], st.secrets["GOC_PASS"])
        }
    except:
        st.error("Error: Configura las credenciales en .streamlit/secrets.toml")
        st.stop()

    with st.spinner("🧠 Analizando mercado y calculando márgenes netos..."):
        params = interpretar(query_input, margen_override=margen_pct / 100)

    async def fetch_safe(func, *args):
        try: return await func(*args)
        except Exception as e:
            st.warning(f"⚠️ Error en fuente: {str(e)}")
            return []

    tasks = []
    if "Cemevisa" in bus_sources:
        tasks.append(fetch_safe(buscar_cemevisa, creds["cem"][0], creds["cem"][1], params["familia"], params.get("marca"), params.get("palabra", ""), params["margen"], 1, True))
    if "Gocisa" in bus_sources:
        tasks.append(fetch_safe(buscar_gocisa, creds["goc"][0], creds["goc"][1], params["familia"], params.get("marca"), params.get("palabra", ""), params["margen"], 1, True))

    raw_results = [p for sublist in asyncio.run(asyncio.gather(*tasks)) for p in sublist]
    
    if not raw_results:
        st.info("No se encontraron coincidencias. Prueba refinando la búsqueda.")
    else:
        # Eliminar duplicados por referencia
        unique = []
        seen = set()
        for r in raw_results:
            if r["Referencia"] not in seen:
                unique.append(r)
                seen.add(r["Referencia"])
        
        ranked = filter_and_rank(unique, params)
        featured = ranked[0]
        alternatives = ranked[1:6]

        # ── RESULTADO DESTACADO ──
        st.markdown(f"## ⭐ Producto Recomendado")
        
        st.markdown(f'''<div class="glass-card" style="display:flex; flex-wrap: wrap; gap:2rem; align-items:flex-start;">
<div class="featured-ribbon">DESTACADO</div>
<div style="flex: 1; min-width: 250px;">
<div class="img-container">
<img src="{featured.get('Imagen') or 'https://via.placeholder.com/400x300?text=No+Image'}" style="max-height:100%; max-width:100%; object-fit: contain;">
</div>
</div>
<div style="flex: 2; min-width: 300px;">
<div class="price-sub">PROVEEDOR: <b>{featured['Fuente']}</b> • REF: {featured['Referencia']}</div>
<h2 style="margin: 0.5rem 0; font-size: 1.8rem;">{featured['Nombre']}</h2>

<div style="background:var(--bg-color); padding:1rem; border-radius:6px; margin: 1rem 0;">
<div style="display:flex; justify-content:space-between; margin-bottom: 0.5rem; font-size: 1.1rem;">
<span>Coste Neto:</span>
<b>{featured['Coste €']:.2f} €</b>
</div>
<div style="display:flex; justify-content:space-between; margin-bottom: 0.5rem; font-size: 1.1rem;">
<span>PVP ({int(params['margen']*100)}% margen):</span>
<div class="price-main">{featured['PVP €']:.2f} €</div>
</div>
<hr style="border-top:1px solid var(--border-light); margin: 0.5rem 0;">
<div style="display:flex; justify-content:space-between; font-size: 1.2rem;">
<span>Beneficio Decoyba:</span>
<span class="profit-text">+{featured['Beneficio €']:.2f} €</span>
</div>
</div>

<a href="{featured['URL']}" target="_blank" class="btn-supplier">COMPRAR EN PROVEEDOR ↗</a>
</div>
</div>
''', unsafe_allow_html=True)

        # ── ALTERNATIVAS ──
        st.markdown("<br><hr style='border:1px solid #E0E0E0'><br>", unsafe_allow_html=True)
        st.markdown("### Otras Opciones Encontradas")
        
        cols = st.columns(3)
        for i, item in enumerate(alternatives[:6]):
            with cols[i % 3]:
                st.markdown(f"""<div class="glass-card" style="margin-bottom:2rem; display:flex; flex-direction:column; height: 100%;">
<div class="img-container">
<img src="{item.get('Imagen') or ''}" style="max-height:100%; max-width:100%; object-fit: contain;">
</div>
<div class="price-sub">{item['Fuente']}</div>
<h4 style="font-size:1.1rem; margin:0.5rem 0; flex-grow: 1;">{item['Nombre']}</h4>
<div style="margin-top:auto;">
<div style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 0.2rem;">Coste neto: <b>{item['Coste €']:.2f} €</b></div>
<div class="price-main" style="font-size:2rem !important;">{item['PVP €']:.2f} €</div>
<div class="profit-text" style="font-size: 0.9rem;">Beneficio: +{item['Beneficio €']:.2f} €</div>
<a href="{item['URL']}" target="_blank" class="btn-supplier" style="padding:0.5rem; font-size:0.9rem;">VER FICHA</a>
</div>
</div>
""", unsafe_allow_html=True)

else:
    # Homepage sencilla
    st.markdown("""
    <div style="text-align: center; padding: 4rem 1rem;">
        <h2 style="font-size: 2.5rem; font-weight: 700; color: var(--brand-main); margin-bottom: 1rem;">Bienvenido al Portal Comercial</h2>
        <p style="font-size: 1.2rem; color: var(--text-muted); max-width: 600px; margin: 0 auto;">
            Utiliza el buscador superior para encontrar productos en Cemevisa y Gocisa de forma simultánea. Los márgenes se aplican automáticamente según la configuración lateral.
        </p>
    </div>
    """, unsafe_allow_html=True)
