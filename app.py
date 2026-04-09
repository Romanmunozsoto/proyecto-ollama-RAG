import gradio as gr
import chromadb
import requests
import os
import unicodedata
import sys

# --- CONFIGURACION ---
URL_BASE = "http://localhost:11434/api"
MODELO_CHAT = "llama3.2"
MODELO_EMBED = "nomic-embed-text"
DB_PATH = "./roman_estore_db"

# --- FUNCIONES DE APOYO ---
def normalizar(texto):
    """Elimina acentos y convierte a minusculas."""
    texto = texto.lower()
    texto = ''.join(c for c in unicodedata.normalize('NFD', texto)
                  if unicodedata.category(c) != 'Mn')
    return texto

def obtener_embedding(texto):
    """Obtiene el embedding usando la API de Ollama[cite: 32, 41]."""
    payload = {"model": MODELO_EMBED, "prompt": texto}
    res = requests.post(f"{URL_BASE}/embeddings", json=payload)
    return res.json()["embedding"]

# --- PARTE 2: CHROMADB (Carga e Indexacion) ---
# Creamos la coleccion persistente para evitar duplicados [cite: 34, 35]
cliente = chromadb.PersistentClient(path=DB_PATH)
coleccion = cliente.get_or_create_collection(name="knowledge_base")

def inicializar_base_datos():
    """Lee archivos de knowledge-base/ y los guarda en ChromaDB[cite: 29, 30]."""
    if coleccion.count() > 0:
        print("Roman-eStore: La base de datos ya contiene informacion.")
        return

    # Ruta correcta segun tu estructura de carpetas 
    directorio = "knowledge-base"
    
    if not os.path.exists(directorio):
        print(f"Error: No se encuentra la carpeta {directorio}")
        return

    ficheros = os.listdir(directorio)
    total = len(ficheros)
    
    for i, nombre_archivo in enumerate(ficheros):
        # Feedback visual de carga en terminal
        progreso = int((i+1)/total*100)
        sys.stdout.write(f"\rCargando base de datos de Roman-eStore: {progreso}%")
        sys.stdout.flush()
        
        ruta_completa = os.path.join(directorio, nombre_archivo)
        with open(ruta_completa, "r", encoding="utf-8") as f:
            contenido = f.read()
            
            # Dividimos el texto en fragmentos (chunking) [cite: 31]
            chunks = [c.strip() for c in contenido.split("\n\n") if c.strip()]
            
            for j, chunk in enumerate(chunks):
                coleccion.add(
                    ids=[f"{nombre_archivo}_{j}"],
                    embeddings=[obtener_embedding(chunk)],
                    documents=[chunk]
                )
    print("\n✅ Roman-eStore: Sistema RAG preparado.")

# --- PARTE 3: FUNCION RAG (Pipeline unico) ---
def responder_chat(pregunta, historial):
    """Busca en ChromaDB y genera respuesta con contexto[cite: 38, 39]."""
    # 1. Recuperacion semantica [cite: 42]
    pregunta_norm = normalizar(pregunta)
    embed_pregunta = obtener_embedding(pregunta_norm)
    
    resultados = coleccion.query(
        query_embeddings=[embed_pregunta],
        n_results=3 # Recuperamos los 3 fragmentos mas relevantes
    )
    contexto = "\n".join(resultados['documents'][0])
    
    # 2. Construccion del prompt con contexto (Aumentacion) [cite: 43]
    prompt = f"""
    Eres el asistente de Roman-eStore. Usa el siguiente contexto para responder de forma amable.
    Si la informacion no esta en el contexto, di que no lo sabes.
    
    CONTEXTO RECUPERADO:
    {contexto}
    
    PREGUNTA DEL USUARIO: {pregunta}
    """
    
    # 3. Generacion con Ollama [cite: 44, 45]
    payload = {
        "model": MODELO_CHAT,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False
    }
    res = requests.post(f"{URL_BASE}/chat", json=payload)
    return res.json()["message"]["content"]

# --- PARTE 4: INTERFAZ GRADIO ---
inicializar_base_datos()

# Solo tienes que quitar la linea del theme para que no de error
demo = gr.ChatInterface(
    fn=responder_chat,
    title="Roman-eStore: Soporte Inteligente RAG",
    description="Bienvenido a la nueva interfaz de Roman-eStore. Consulta dudas sobre envios, productos y garantias.",
    examples=["¿Cual es vuestro horario?", "¿Que garantia tienen los moviles?", "¿Cuanto tarda un envio?"]
)

if __name__ == "__main__":
    demo.launch()