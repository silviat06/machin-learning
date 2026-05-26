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

    # Términos de búsqueda básicos
    terminos = [
        "choque fatal",
        "accidente de tránsito muerto",
        "siniestro vial fallecido",
        "accidente colectivo",
        "choque múltiple"
    ]

    # Construir las queries basadas en el input del usuario
    queries = []
    # Limpiamos el input del medio por si puso "https://www..." o similar
    medio_limpio = medio.replace("https://", "").replace("http://", "").replace("www.", "").strip()
    # Si medio_limpio tiene un '/' al final, se lo sacamos
    if medio_limpio.endswith("/"):
        medio_limpio = medio_limpio[:-1]

    for termino in terminos:
        if medio_limpio:
            queries.append(f"{termino} {año_fecha} site:{medio_limpio}")
        else:
            # Si no puso medio, busca en general en la provincia
            queries.append(f"{termino} {año_fecha} provincia de buenos aires")

    urls_seen = set()

    from duckduckgo_search import DDGS
    with DDGS() as ddgs:
        for q in queries:
            try:
                # Pausa para evitar rate limits
                time.sleep(2)
                results = list(ddgs.text(q, max_results=15))
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
                    # Extraer el año que buscamos (ej. '2023' de '2023' o '2023-05' de '2023-05-21')
                    año_str = str(año_fecha)[:4] if año_fecha else '2023'

                    # Buscar fecha en el link (formato 2023/05/21 o 2023-05-21)
                    match = re.search(r'202[2-5][/-]\d{2}[/-]\d{2}', url)
                    if match:
                        fecha = match.group(0).replace('/', '-')
                    elif r.get('date'):
                        fecha = r.get('date')[:10]

                    # Validacion de año
                    if fecha and año_str not in fecha:
                        continue

                    if not fecha:
                        if año_str not in url and año_str not in text:
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
                print(f"Error buscando {q}: {e}")

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
