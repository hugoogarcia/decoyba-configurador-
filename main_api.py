from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import asyncio
import time
from interpreter import interpretar
from cemevisa_scraper import buscar_cemevisa
from gocisa_scraper import buscar_gocisa
import os
from dotenv import load_dotenv

# Cargar variables de entorno (para desarrollo local)
load_dotenv()

app = FastAPI(title="DECOYBA Elite API")

# Configurar CORS para que el frontend pueda conectar
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, restringir a los dominios autorizados
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "online", "message": "DECOYBA Elite API is running"}

@app.get("/search")
async def search(
    query: str,
    margen: float = Query(0.40, ge=0.20, le=0.60),
    sources: List[str] = Query(["Cemevisa", "Gocisa"])
):
    """
    Endpoint principal de búsqueda. Interpreta la consulta y busca en los proveedores.
    """
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    try:
        # 1. Interpretar con IA
        params = interpretar(query, margen_override=margen)
        
        # 2. Ejecutar scrapers en paralelo
        tasks = []
        
        # Preparar credenciales (en producción vendrán de env vars)
        # Nota: En Streamlit se usaba st.secrets, aquí usaremos os.environ
        # o valores por defecto del archivo secrets original para desarrollo
        cem_user = os.getenv("CEM_USER", "13323")
        cem_pass = os.getenv("CEM_PASS", "2h74")
        goc_user = os.getenv("GOC_USER", "luis@decoyba.com")
        goc_pass = os.getenv("GOC_PASS", "DC151618")

        async def fetch_safe(func, *args):
            try:
                return await func(*args)
            except Exception as e:
                print(f"Error en scraper: {str(e)}")
                return []

        if "Cemevisa" in sources:
            tasks.append(fetch_safe(buscar_cemevisa, cem_user, cem_pass,
                                    params["familia"], params.get("marca"), params.get("palabra", ""),
                                    params["margen"], 2, True))
        
        if "Gocisa" in sources:
            tasks.append(fetch_safe(buscar_gocisa, goc_user, goc_pass,
                                    params["familia"], params.get("marca"), params.get("palabra", ""),
                                    params["margen"], 2, True))

        all_results = await asyncio.gather(*tasks)
        raw_results = [p for sublist in all_results for p in sublist]

        # 3. Procesar resultados (eliminar duplicados y ordenar)
        unique_results = []
        seen_refs = set()
        for r in raw_results:
            if r["Referencia"] not in seen_refs:
                unique_results.append(r)
                seen_refs.add(r["Referencia"])
        
        # Ordenar por beneficio de mayor a menor
        ranked_results = sorted(unique_results, key=lambda x: x["Beneficio €"], reverse=True)

        return {
            "query": query,
            "params": params,
            "results_count": len(ranked_results),
            "results": ranked_results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
