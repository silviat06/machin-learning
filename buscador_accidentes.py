# Para ejecutar este script, primero debes instalar las dependencias necesarias.
# Puedes hacerlo ejecutando en tu terminal:
# pip install pandas spacy duckduckgo-search newspaper3k lxml_html_clean
# python -m spacy download es_core_news_sm
#
# Si estás en Jupyter Notebook o Google Colab, ejecuta esto en una celda:
# !pip install pandas spacy duckduckgo-search newspaper3k lxml_html_clean
# !python -m spacy download es_core_news_sm

import pandas as pd
import spacy

from newspaper import Article
import time
import os
import re
try:
    from IPython.display import display
except ImportError:
    display = print

# Cargar modelo de NLP
try:
    nlp = spacy.load("es_core_news_sm")
except OSError:
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "es_core_news_sm"])
    nlp = spacy.load("es_core_news_sm")


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

    # Extraer lugares con NER
    lugares_encontrados = []
    for ent in doc.ents:
        if ent.label_ == "LOC":
             if ent.text.lower() not in ["buenos aires", "provincia", "argentina", "pba", "provincia de buenos aires"]:
                 lugares_encontrados.append(ent.text)

    if lugares_encontrados:
        info['Lugar'] = lugares_encontrados[0]

    text_lower = text.lower()

    # Palabras clave para condiciones
    if any(word in text_lower for word in ['muerto', 'fallecid', 'víctima fatal', 'vida', 'mortal', 'muerte', 'falleció', 'murieron', 'víctimas']):
         info['Fallecidos'] = 'Sí'
    if any(word in text_lower for word in ['herid', 'lesionad', 'hospitalizad', 'hospital', 'politraumatismos']):
         info['Heridos'] = 'Sí'
    if any(word in text_lower for word in ['ileso', 'sin heridas', 'fuera de peligro', 'salvó su vida']):
         info['Ilesos'] = 'Sí'

    # Palabras clave para sexo
    if any(word in text_lower for word in ['hombre', 'masculino', 'chico']):
        info['Sexo'] = 'Masculino'
    if any(word in text_lower for word in ['mujer', 'femenino', 'chica']):
        if info['Sexo'] == 'Masculino':
            info['Sexo'] = 'Ambos / Mixto'
        else:
             info['Sexo'] = 'Femenino'

    # Palabras clave para tipo de vía
    if 'ruta' in text_lower or 'rp' in text_lower or 'rn' in text_lower:
        info['Tipo Via'] = 'Ruta'
    elif 'autopista' in text_lower or 'panamericana' in text_lower or 'acceso' in text_lower:
        info['Tipo Via'] = 'Autopista'
    elif 'calle' in text_lower or 'avenida' in text_lower or 'esquina' in text_lower:
        info['Tipo Via'] = 'Urbana'

    # Palabras clave para vehículos
    vehiculos = ['auto', 'automóvil', 'camión', 'moto', 'motocicleta', 'colectivo',
        'bicicleta', 'camioneta', 'tren', 'micro', 'ómnibus', 'utilitario']
    for v in vehiculos:
         if re.search(r'\b' + re.escape(v) + r'\b', text_lower):
              info['Vehiculos'].append(v)

    # Extracción de edad básica
    ages = re.findall(r'\b(\d{1,2})\s*años\b', text_lower)
    if ages:
         info['Edad'] = ", ".join(set(ages)) + " años"

    return info


def fetch_and_process_data():
    all_data = []
    # Ampliamos la búsqueda y forzamos el año 2023 en las queries
    # Lista de medios locales/regionales de la Provincia de Buenos Aires
    medios_pba = [
        "eldia.com",          # La Plata
        "infocielo.com",      # Provincial
        "lanueva.com",        # Bahía Blanca
        "lacapitalmdp.com",   # Mar del Plata
        "inforegion.com.ar",  # Zona Sur GBA
        "0223.com.ar",        # Mar del Plata
        "elpopular.com.ar",   # Olavarría
        "diarioepoca.com",    # General
        "latecla.info",       # Provincial
        "elmarplatense.com",  # Mar del Plata
        "infobrisas.com",     # Mar del Plata
        "zonanortediario.com.ar", # Zona Norte GBA
        "pilaradiario.com",   # Pilar
        "clarin.com",         # Nacional (sección zonal)
        "lanacion.com.ar",    # Nacional
        "infobae.com"         # Nacional
    ]

    # Términos de búsqueda básicos
    terminos = [
        "choque fatal",
        "accidente de tránsito muerto",
        "siniestro vial fallecido"
    ]

    # Generamos combinaciones exhaustivas (Termino + Año + site:Medio)
    queries = []
    for medio in medios_pba:
        for termino in terminos:
            queries.append(f"{termino} 2023 site:{medio}")

    urls_seen = set()


    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        for q in queries:
            try:
                # Usamos ddgs.text() que es más exhaustivo históricamente que ddgs.news()
                # Pausa para evitar rate limits
                time.sleep(2)

                results = list(ddgs.text(q, max_results=20))
                for r in results:
                    url = r.get('href')
                    if not url or url in urls_seen:
                        continue
                    urls_seen.add(url)

                    try:
                        article = Article(url)
                        article.download()
                        article.parse()
                        text = article.text
                        title = article.title

                        if not text:
                            text = r.get('body', '') + " " + r.get('title', '')
                    except Exception:
                        text = r.get('body', '') + " " + r.get('title', '')
                        title = r.get('title', '')

                    if not text:
                        continue

                    fecha = ''
                    match = re.search(r'202[2-5]/\d{2}/\d{2}', url)
                    if match:
                        fecha = match.group(0).replace('/', '-')
                    elif r.get('date'):
                        fecha = r.get('date')[:10]

                    if fecha and '2023' not in fecha:
                        continue

                    if not fecha:
                        if '2023' not in url and '2023' not in text:
                            continue
                        fecha = '2023'

                    info = extract_info(text)
                    all_data.append({
                        'Fecha': fecha,
                        'Lugar': info['Lugar'],
                        'Fallecidos': info['Fallecidos'],
                        'Heridos': info['Heridos'],
                        'Ilesos': info['Ilesos'],
                        'Sexo': info['Sexo'],
                        'Edad': info['Edad'],
                        'Tipo Via': info['Tipo Via'],
                        'Vehiculos Involucrados': ", ".join(info['Vehiculos']) if info['Vehiculos'] else "No especificado",
                        'Titulo': title,
                        'Link': url
                    })
            except Exception as e:
                print(f"Error buscando {q}: {e}")

    return pd.DataFrame(all_data)

if __name__ == "__main__":
    print("Iniciando búsqueda y extracción de datos. Esto puede tardar unos minutos...")
    df_accidentes = fetch_and_process_data()

    if not df_accidentes.empty:
        print(f"\n¡Completado! Se encontraron {len(df_accidentes)} noticias de accidentes de 2023.")

        # Guardar a CSV en la ruta especificada
        output_dir = r"D:\vial"
        try:
            os.makedirs(output_dir, exist_ok=True)
            csv_filename = os.path.join(output_dir, 'accidentes_transito_pba_2023.csv')
            df_accidentes.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            print(f"Datos guardados exitosamente en el archivo: {csv_filename}\n")
        except OSError as e:
            print(f"\nNo se pudo crear la ruta {output_dir}. Guardando en el directorio actual...")
            csv_filename = 'accidentes_transito_pba_2023.csv'
            df_accidentes.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            print(f"Datos guardados en el archivo: {csv_filename}\n")

        # Mostrar primeras filas
        display(df_accidentes.head(10))
    else:
        print("No se encontraron resultados para la búsqueda.")
