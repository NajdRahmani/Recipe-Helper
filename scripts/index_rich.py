"""Index one chunk per recipe (name + ingredients) with the full recipe in the payload.
Usage: python scripts/index_rich.py [N_RECIPES]   (default 6000)"""
import ast, sys
import pandas as pd
import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, PayloadSchemaType

N = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
COLLECTION = "recipes_rich"
BATCH = 32

df = pd.read_csv("data/RAW_recipes.csv").dropna(subset=["name"]).head(N)
q = QdrantClient(url="http://localhost:6333")
if q.collection_exists(COLLECTION):
    q.delete_collection(COLLECTION)
q.create_collection(COLLECTION, vectors_config=VectorParams(size=1024, distance=Distance.COSINE))
q.create_payload_index(COLLECTION, "minutes", PayloadSchemaType.INTEGER)
q.create_payload_index(COLLECTION, "tags", PayloadSchemaType.KEYWORD)

rows = []
for pid, r in df.iterrows():
    ing = ast.literal_eval(r["ingredients"])
    steps = ast.literal_eval(r["steps"])
    if len(ing) < 3 or len(steps) < 2:
        continue  # skip very thin recipes
    rows.append((int(pid), {
        "name": r["name"].strip(),
        "minutes": int(r["minutes"]),
        "ingredients": ing,
        "steps": steps,
        "tags": ast.literal_eval(r["tags"]),
        "n_ingredients": len(ing),
    }))

done = 0
for i in range(0, len(rows), BATCH):
    chunk = rows[i:i + BATCH]
    texts = [f"{p['name']}. Ingredients: {', '.join(p['ingredients'])}" for _, p in chunk]
    vecs = ollama.embed(model="bge-m3", input=texts)["embeddings"]
    q.upsert(COLLECTION, [PointStruct(id=pid, vector=v, payload=p) for (pid, p), v in zip(chunk, vecs)])
    done += len(chunk)
    if done % 640 < BATCH:
        print(COLLECTION, done, "/", len(rows), flush=True)
print(COLLECTION, "done", done)
