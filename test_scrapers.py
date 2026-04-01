import asyncio
from cemevisa_scraper import buscar_cemevisa
from gocisa_scraper import buscar_gocisa
import streamlit as st

async def test():
    print("--- Probando Cemevisa ---")
    try:
        res_cem = await buscar_cemevisa(
            usuario="13323",
            clave="2h74",
            familia="hornos",
            marca="balay",
            max_paginas=1,
            headless=True
        )
        print(f"Cemevisa: {len(res_cem)} productos encontrados")
    except Exception as e:
        print(f"Error Cemevisa: {e}")

    print("\n--- Probando Gocisa ---")
    try:
        res_goc = await buscar_gocisa(
            usuario="luis@decoyba.com",
            clave="DC151618",
            familia="hornos",
            marca="balay",
            max_paginas=1,
            headless=True
        )
        print(f"Gocisa: {len(res_goc)} productos encontrados")
        if res_goc:
            for r in res_goc[:3]:
                print(f"  - {r['Nombre']} | Coste: {r['Coste €']}€")
    except Exception as e:
        print(f"Error Gocisa: {e}")

if __name__ == "__main__":
    asyncio.run(test())
