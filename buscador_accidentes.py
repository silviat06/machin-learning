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


def fetch_and_process_data(medio, año_fecha):
    all_data = []
    urls_seen = set()
    medio_limpio = medio.replace("https://", "").replace("http://", "").replace("www.", "").strip()
    if medio_limpio.endswith("/"):
        medio_limpio = medio_limpio[:-1]

    # Estrategia 1: Scraping directo de tags internos (muy efectivo para diarios locales como 0221, inforegion, etc)
    if medio_limpio:
        print("\n[Estrategia 1] Intentando recuperar noticias desde secciones y etiquetas internas del medio...")
        secciones = [
            "/tag/accidentes-de-transito", "/tag/accidente", "/tag/choque", "/tag/siniestro-vial",
            "/seccion/policiales", "/policiales", "/categoria/policiales"
        ]
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        for sec in secciones:
            url_seccion = f"https://www.{medio_limpio}{sec}"
            try:
                import requests
                from bs4 import BeautifulSoup
                res = requests.get(url_seccion, headers=headers, timeout=5)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    # Extraer links que parezcan noticias
                    for a in soup.find_all('a', href=True):
                        href = a['href']
                        if 'javascript' in href or '#' in href or '/tag/' in href: continue
                        if not href.startswith('http'):
                            href = f"https://www.{medio_limpio}" + href if href.startswith('/') else f"https://www.{medio_limpio}/{href}"

                        # Filtro simple para que parezca una noticia (tiene guiones y es largo)
                        if '-' in href and len(href) > 35 and href not in urls_seen and medio_limpio in href:
                            urls_seen.add(href)
            except Exception:
                pass

    # Estrategia 2: Búsqueda vía motor global (DuckDuckGo Text)
    print("\n[Estrategia 2] Buscando vía motor web global (DuckDuckGo)...")
    terminos = [
        "choque fatal",
        "accidente de tránsito muerto",
        "siniestro vial fallecido",
        "accidente colectivo",
        "choque múltiple"
    ]

    queries = []
    for termino in terminos:
        if medio_limpio:
            queries.append(f"{termino} {año_fecha} site:{medio_limpio}")
        else:
            queries.append(f"{termino} {año_fecha} provincia de buenos aires")

    from duckduckgo_search import DDGS
    try:
        with DDGS() as ddgs:
            for q in queries:
                try:
                    time.sleep(2)
                    results = list(ddgs.text(q, max_results=10))
                    for r in results:
                        url = r.get('href')
                        if url and url not in urls_seen:
                            urls_seen.add(url)
                except Exception as e:
                    pass
    except Exception as e:
        print("Aviso: El motor global rechazó la conexión. Se usarán únicamente los enlaces internos recuperados.")

    print(f"\nSe recolectaron {len(urls_seen)} enlaces crudos para analizar. Procesando...")

    # Procesar todos los URLs encontrados (internos y externos)
    for url in list(urls_seen): # No limit para no colgar la máquina
        try:
            from newspaper import Config
            config = Config()
            config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
            config.request_timeout = 10

            article = Article(url, config=config)
            article.download()
            article.parse()
            text = article.text
            title = article.title

            if not text:
                continue


            fecha = ''
            año_str = str(año_fecha)[:4] if año_fecha else '2023'

            match = re.search(r'202[2-5][/-]\d{2}[/-]\d{2}', url)
            if match:
                fecha = match.group(0).replace('/', '-')
            elif article.publish_date:
                fecha = str(article.publish_date)[:10]

            # Filter strictly by the requested year if a date was found
            if fecha and año_str not in fecha:
                continue

            # If no date was found in the URL or article metadata, look for the year in the body text.
            # If it's not there either, we discard the article to guarantee no contamination from other years.
            if not fecha:
                if año_str not in text and año_str not in url:
                    continue
                fecha = str(año_fecha)


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
            print('Error en articulo:', e)
            pass

    return pd.DataFrame(all_data)

if __name__ == "__main__":
    print("="*60)
    print("   Buscador Focalizado de Accidentes de Tránsito - PBA   ")
    print("="*60)

    print("\nPor favor, completa los siguientes datos (o presiona Enter para usar los valores por defecto).")

    medio_input = input("1. Ingresa la página web del medio local (ej. inforegion.com.ar): ").strip()
    anio_input = input("2. Ingresa el año o fecha a verificar (ej. 2023 o 2023-05-21) [Por defecto 2023]: ").strip()

    if not anio_input:
        anio_input = "2023"

    print(f"\nIniciando búsqueda focalizada en '{medio_input or 'medios generales'}' para la fecha '{anio_input}'...")
    print("Esto puede tardar unos minutos...")

    df_accidentes = fetch_and_process_data(medio_input, anio_input)

    if not df_accidentes.empty:
        print(f"\n¡Completado! Se encontraron {len(df_accidentes)} noticias de accidentes.")

        # Guardar a CSV en la ruta especificada
        output_dir = r"D:\vial"
        medio_str = medio_input.replace(".", "_") if medio_input else "general"
        archivo_nombre = f'accidentes_{medio_str}_{anio_input}.csv'

        try:
            os.makedirs(output_dir, exist_ok=True)
            csv_filename = os.path.join(output_dir, archivo_nombre)
            df_accidentes.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            print(f"Datos guardados exitosamente en el archivo: {csv_filename}\n")
        except OSError as e:
            print(f"\nNo se pudo crear la ruta {output_dir}. Guardando en el directorio actual...")
            csv_filename = archivo_nombre
            df_accidentes.to_csv(csv_filename, index=False, encoding='utf-8-sig')
            print(f"Datos guardados en el archivo: {csv_filename}\n")

        # Mostrar primeras filas
        display(df_accidentes.head(10))
    else:
        print("\nNo se encontraron resultados para la búsqueda.")
        print("Intenta con un formato de fecha diferente o asegúrate de que el medio tenga la noticia indexada.")
