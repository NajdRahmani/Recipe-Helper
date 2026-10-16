import pandas as pd, ollama
from qdrant_client import QdrantClient

q = QdrantClient(url="http://localhost:6333")
qs = pd.read_csv("eval/queries.csv")
COLLECTIONS = ["recipes_fixed", "recipes_struct", "recipes_rich_2k", "recipes_rich","recipes_v4"]


def run(col, k):
    hits, rr = 0, 0
    for _, row in qs.iterrows():
        v = ollama.embed(model="bge-m3", input=[row["query"]])["embeddings"][0]
        names = [p.payload["name"] for p in q.query_points(col, query=v, limit=k).points]
        if row["expected_name"] in names:
            hits += 1
            rr += 1 / (names.index(row["expected_name"]) + 1)
    print(f"{col} k={k}: hit@k={hits/len(qs):.2f} MRR={rr/len(qs):.2f}")


for col in COLLECTIONS:
    if not q.collection_exists(col):
        print(col, "not found, skipped")
        continue
    for k in [3, 5, 10]:
        run(col, k)
