import streamlit as st
import pandas as pd
import spacy
from duckduckgo_search import DDGS
from newspaper import Article
import time
import re

# Asegurarse de que el modelo esté descargado
try:
    nlp = spacy.load("es_core_news_sm")
except OSError:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "es_core_news_sm"])
    nlp = spacy.load("es_core_news_sm")

st.set_page_config(layout="wide")
st.title("Buscador de Accidentes de Tránsito - Provincia de Buenos Aires (2023)")

st.write("Esta aplicación busca noticias de accidentes de tránsito en la Provincia de Buenos Aires ocurridos en 2023 y extrae información relevante de cada uno mediante Procesamiento de Lenguaje Natural (NLP).")

def extract_info(text):
    doc = nlp(text)

    info = {
        'Lugar': 'Provincia de Buenos Aires (no especificado)',
        'Fallecidos': 'No',
        'Heridos': 'No',
        'Ilesos': 'No',
        'Sexo': 'No especificado',
        'Edad': 'No especificado',
        'Tipo Via': 'No especificado',
        'Vehiculos': []
    }

    # Extract locations using NER
    lugares_encontrados = []
    for ent in doc.ents:
        if ent.label_ == "LOC":
             # filter out generic locations
             if ent.text.lower() not in ["buenos aires", "provincia", "argentina", "pba", "provincia de buenos aires"]:
                 lugares_encontrados.append(ent.text)

    if lugares_encontrados:
        info['Lugar'] = lugares_encontrados[0] # Take the first specific location found

    text_lower = text.lower()

    # Keywords for conditions
    if any(word in text_lower for word in ['muerto', 'fallecid', 'víctima fatal', 'vida', 'mortal', 'muerte', 'falleció', 'murieron', 'víctimas']):
         info['Fallecidos'] = 'Sí'
    if any(word in text_lower for word in ['herid', 'lesionad', 'hospitalizad', 'hospital', 'politraumatismos']):
         info['Heridos'] = 'Sí'
    if any(word in text_lower for word in ['ileso', 'sin heridas', 'fuera de peligro', 'salvó su vida']):
         info['Ilesos'] = 'Sí'

    # Keywords for sex
    if any(word in text_lower for word in ['hombre', 'masculino', 'chico']):
        info['Sexo'] = 'Masculino'
    if any(word in text_lower for word in ['mujer', 'femenino', 'chica']):
        if info['Sexo'] == 'Masculino':
            info['Sexo'] = 'Ambos / Mixto'
        else:
             info['Sexo'] = 'Femenino'

    # Keywords for road type
    if 'ruta' in text_lower or 'rp' in text_lower or 'rn' in text_lower:
        info['Tipo Via'] = 'Ruta'
    elif 'autopista' in text_lower or 'panamericana' in text_lower or 'acceso' in text_lower:
        info['Tipo Via'] = 'Autopista'
    elif 'calle' in text_lower or 'avenida' in text_lower or 'esquina' in text_lower:
        info['Tipo Via'] = 'Urbana'

    # Keywords for vehicles
    vehiculos = ['auto', 'automóvil', 'camión', 'moto', 'motocicleta', 'colectivo', 'bicicleta', 'camioneta', 'tren', 'micro', 'ómnibus', 'utilitario']
    for v in vehiculos:
         if re.search(r'\b' + re.escape(v) + r'\b', text_lower):
              info['Vehiculos'].append(v)

    # basic age extraction (regex)
    ages = re.findall(r'\b(\d{1,2})\s*años\b', text_lower)
    if ages:
         info['Edad'] = ", ".join(set(ages)) + " años"

    return info

@st.cache_data(ttl=3600)
def fetch_and_process_data():
    all_data = []
    queries = [
        "accidente transito fatal provincia de buenos aires 2023",
        "choque ruta provincia de buenos aires 2023",
        "accidente colectivo pba 2023",
        "choque múltiple panamericana 2023",
        "accidente moto provincia de buenos aires 2023"
    ]
    urls_seen = set()

    with DDGS() as ddgs:
        for q in queries:
            try:
                # Use news search
                results = list(ddgs.news(q, max_results=10))
                for r in results:
                    url = r.get('url')
                    if not url or url in urls_seen:
                        continue
                    urls_seen.add(url)

                    try:
                        article = Article(url)
                        article.download()
                        article.parse()
                        text = article.text
                        if not text:
                            text = r.get('body', '') + " " + r.get('title', '')
                    except Exception:
                        text = r.get('body', '') + " " + r.get('title', '')

                    if not text: continue

                    info = extract_info(text)
                    all_data.append({
                        'Fecha': r.get('date', '')[:10] if r.get('date') else '',
                        'Lugar': info['Lugar'],
                        'Fallecidos': info['Fallecidos'],
                        'Heridos': info['Heridos'],
                        'Ilesos': info['Ilesos'],
                        'Sexo': info['Sexo'],
                        'Edad': info['Edad'],
                        'Tipo Via': info['Tipo Via'],
                        'Vehiculos Involucrados': ", ".join(info['Vehiculos']) if info['Vehiculos'] else "No especificado",
                        'Titulo': r.get('title', ''),
                        'Link': url
                    })
            except Exception as e:
                print(f"Error fetching {q}: {e}")

    return pd.DataFrame(all_data)

if st.button("Buscar y Extraer Datos"):
    with st.spinner('Buscando y procesando noticias en diarios digitales... Esto puede tardar unos minutos.'):
        df = fetch_and_process_data()

    if not df.empty:
        st.success(f"Se encontraron y procesaron {len(df)} noticias de accidentes.")
        st.dataframe(
            df,
            column_config={
                "Link": st.column_config.LinkColumn("Enlace a la Noticia")
            },
            hide_index=True,
            use_container_width=True
        )

        # Download button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar datos en formato CSV",
            data=csv,
            file_name='accidentes_transito_pba_2023.csv',
            mime='text/csv',
        )
    else:
        st.warning("No se encontraron resultados para la búsqueda.")
