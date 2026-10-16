# scripts/reindex_ft.py
import pandas as pd
import ast
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient, models

model = SentenceTransformer("models/bge-ft")
q = QdrantClient("http://localhost:6333")

# Recreate collection
q.delete_collection("recipes_ft")
q.create_collection("recipes_ft", vectors_config=models.VectorParams(size=1024, distance=models.Distance.COSINE))

# Index
df = pd.read_csv("data/RAW_recipes.csv").dropna(subset=["name"]).head(60000)
batch = []
for i, row in df.iterrows():
    try:
        ing = ast.literal_eval(row["ingredients"])
        if len(ing) < 3: continue
    except: continue
    
    text = f"{row['name']}. Ingredients: {', '.join(ing[:15])}"
    vec = model.encode(text).tolist()
    
    batch.append(models.PointStruct(
        id=i,
        vector=vec,
        payload={"name": row["name"], "ingredients": ing, "minutes": int(row["minutes"])}
    ))
    
    if len(batch) >= 64:
        q.upsert("recipes_ft", batch)
        batch = []
        if i % 10000 == 0: print(f"{i}/60000")

if batch: q.upsert("recipes_ft", batch)
print("Done")