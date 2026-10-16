"""
index_v4.py - Index the single-dataset KB (Food.com) into Qdrant for Recipe Helper v4.

Usage: python scripts/index_v4.py [N] [COLLECTION]
Defaults: all recipes, collection recipes_v4
"""
import sys

import numpy as np
import pandas as pd
import ollama
from qdrant_client import QdrantClient
from qdrant_client.models import (Distance, PayloadSchemaType, PointStruct,
                                  VectorParams)

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
COLLECTION = sys.argv[2] if len(sys.argv) > 2 else "recipes_v4"
BATCH = 32
QDRANT_URL = "http://localhost:6333"
PARQUET = "data/recipes_single.parquet"


def as_list(x):
    """Parquet round-trip gives numpy arrays; normalize to Python lists."""
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, (list, tuple)):
        return list(x)
    return []


def num(x):
    return None if pd.isna(x) else x


# ---------------------------------------------------------------- load & prep
df = pd.read_parquet(PARQUET)
print(f"Loaded {len(df)} rows from {PARQUET}")

# normalize list-like columns
for col in ["ingredients", "steps", "ingredient_lines", "tags"]:
    df[col] = df[col].apply(as_list)

# --- schema adaptation: derive fields the bot expects ---
df["vegetarian"] = df["tags"].apply(lambda t: "vegetarian" in t)
df["cuisine_type"] = df["cuisine"]

# ---------------------------------------------------------------- quality filter
df = df[(df["ingredients"].str.len() >= 3) & (df["steps"].str.len() >= 2)]
if df.empty:
    raise SystemExit(
        "ERROR: 0 recipes passed the quality filter. The single parquet is "
        "probably corrupted - re-run scripts/prep_single.py first."
    )

df = df.head(N).reset_index(drop=True)
print(f"Indexing {len(df)} recipes into '{COLLECTION}'...")

# ---------------------------------------------------------------- collection
q = QdrantClient(url=QDRANT_URL)
if q.collection_exists(COLLECTION):
    q.delete_collection(COLLECTION)
q.create_collection(
    COLLECTION,
    vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
)
for field, typ in [
    ("minutes", PayloadSchemaType.INTEGER),
    ("vegetarian", PayloadSchemaType.BOOL),
    ("calories_per_serving", PayloadSchemaType.INTEGER),
    ("cuisine_type", PayloadSchemaType.KEYWORD),
]:
    q.create_payload_index(COLLECTION, field, typ)

# ---------------------------------------------------------------- index
for start in range(0, len(df), BATCH):
    rows = df.iloc[start:start + BATCH].to_dict("records")
    texts = [f"{r['name']}. Ingredients: {', '.join(r['ingredients'])}" for r in rows]
    vecs = ollama.embed(model="bge-m3", input=texts)["embeddings"]
    q.upsert(
        COLLECTION,
        points=[
            PointStruct(
                id=start + i,
                vector=vecs[i],
                payload={
                    "name": r["name"],
                    "minutes": num(r["minutes"]),
                    "ingredients": r["ingredients"],
                    "steps": r["steps"],
                    "ingredient_lines": r["ingredient_lines"] or None,
                    "calories_per_serving": (
                        None if pd.isna(r["kcal"]) else int(round(r["kcal"]))
                    ),
                    "protein_g": num(r["protein_g"]),
                    "carbs_g": num(r["carbs_g"]),
                    "fat_g": num(r["fat_g"]),
                    "vegetarian": bool(r["vegetarian"]),
                    "cuisine_type": r["cuisine_type"] or None,
                    "image_url": r["image_url"] if pd.notna(r["image_url"]) else None,
                },
            )
            for i, r in enumerate(rows)
        ],
    )
    if start % 3200 == 0:
        print(f"  {start}/{len(df)}", flush=True)

# ---------------------------------------------------------------- verify
count = q.count(COLLECTION).count
print(f"Done: {count} points in '{COLLECTION}'")

sample, _ = q.scroll(COLLECTION, limit=1, with_payload=True)
p = sample[0].payload
missing = [k for k in ["name", "ingredients", "steps", "calories_per_serving",
                       "protein_g", "carbs_g", "fat_g"] if p.get(k) is None]
if missing:
    print(f"WARNING: sample point missing fields: {missing}")
else:
    print(f"Sample OK: {p['name']} | {p['calories_per_serving']} kcal | "
          f"{p['protein_g']}g P / {p['carbs_g']}g C / {p['fat_g']}g F")