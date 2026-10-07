import ast
import pandas as pd
import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

N = 2000
df = pd.read_csv("data/RAW_recipes.csv").dropna(subset=["name"]).head(N)
q = QdrantClient(url="http://localhost:6333")

def embed(texts):
    return ollama.embed(model="bge-m3", input=texts)["embeddings"]

def full_text(r):
    ing = ", ".join(ast.literal_eval(r["ingredients"]))
    steps = " ".join(ast.literal_eval(r["steps"]))
    return f"{r['name']}\nIngredients: {ing}\nSteps: {steps}"

def chunks_fixed(r, size=800, overlap=100):
    t = full_text(r)
    return [t[i:i+size] for i in range(0, len(t), size - overlap)]

def chunks_struct(r):
    ing = ", ".join(ast.literal_eval(r["ingredients"]))
    steps = " ".join(ast.literal_eval(r["steps"]))
    tags = ", ".join(ast.literal_eval(r["tags"])[:8])
    head = f"{r['name']} | tags: {tags}"
    return [f"{head}\nIngredients: {ing}", f"{head}\nSteps: {steps}"]

def build(collection, chunker):
    if q.collection_exists(collection):
        q.delete_collection(collection)
    q.create_collection(collection, vectors_config=VectorParams(size=1024, distance=Distance.COSINE))
    pid = 0
    for _, r in df.iterrows():
        cs = chunker(r)
        vecs = embed(cs)
        pts = []
        for c, v in zip(cs, vecs):
            pts.append(PointStruct(id=pid, vector=v, payload={"name": r["name"], "minutes": int(r["minutes"]), "text": c}))
            pid += 1
        q.upsert(collection, pts)
        if pid % 500 < len(cs):
            print(collection, pid, flush=True)
    print(collection, "done", pid)

build("recipes_fixed", chunks_fixed)
build("recipes_struct", chunks_struct)
