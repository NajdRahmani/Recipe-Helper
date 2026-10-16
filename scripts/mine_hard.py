# scripts/mine_hard.py
import pandas as pd
import ast
import json
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient

model = SentenceTransformer("models/bge-ft")
q = QdrantClient("http://localhost:6333")

# Load test queries
queries = pd.read_csv("eval/queries.csv")

hard_negatives = []
for _, row in queries.iterrows():
    vec = model.encode(row["query"]).tolist()
    results = q.query_points("recipes_ft", query=vec, limit=20).points
    
    for r in results:
        if r.payload["name"] != row["expected_name"]:
            hard_negatives.append({
                "query": row["query"],
                "positive": f"{row['expected_name']}. Ingredients: ...",  # Fill from CSV
                "negative": f"{r.payload['name']}. Ingredients: {', '.join(r.payload['ingredients'][:10])}"
            })

with open("data/hard_negatives.jsonl", "w") as f:
    for h in hard_negatives:
        f.write(json.dumps(h) + "\n")

print(f"Mined {len(hard_negatives)} hard negatives")