# Configurador de Producto DECOYBA — Instalación

## Requisitos
- Python 3.10 o superior
- Clave API de Anthropic (para el intérprete IA)

## Instalación (una sola vez)

```bash
# 1. Entra a la carpeta
cd ruta/a/configurador

# 2. Instala dependencias
pip install -r requirements.txt

# 3. Instala el navegador Chromium (para el scraper)
playwright install chromium

# 4. Añade tu API key de Anthropic en el archivo de secrets
#    Edita .streamlit/secrets.toml y pon tu clave:
#    ANTHROPIC_API_KEY = "sk-ant-..."
```

## Arrancar la app

```bash
streamlit run app.py
```

Se abrirá automáticamente en tu navegador en `http://localhost:8501`

## Uso

1. Escribe qué buscas en lenguaje natural, por ejemplo:
   - `horno Balay barato pero bueno`
   - `nevera Bosch de calidad para piso de lujo`
   - `lavavajillas que no sea caro, marca da igual`
   - `placa de inducción Siemens alta gama`

2. Ajusta el margen con el slider (por defecto 40%)

3. Pulsa **Buscar en Cemevisa**

4. La tabla aparece ordenada de mayor a menor beneficio

## Familias disponibles
hornos, frio/nevera, lavadora, lavavajillas, placas, campana, microondas, secadora

## Marcas disponibles
Balay, Bosch, Siemens, AEG, Electrolux, Cata, Teka, Beko, Hisense, Samsung, LG, Whirlpool, Neff

## Nota sobre Gocisa
El portal de Gocisa (`grupo.gocisa.es`) es una intranet privada que solo es accesible
desde las oficinas o red VPN de Gocisa. Por ahora, la herramienta conecta únicamente con Cemevisa.
