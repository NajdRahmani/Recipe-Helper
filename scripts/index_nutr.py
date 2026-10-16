import pandas as pd, ollama
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, PayloadSchemaType

COLLECTION, BATCH = "recipes_nutr", 32
df = pd.read_parquet("../data/recipes_kb.parquet").reset_index(drop=True)

q = QdrantClient(url="http://localhost:6333")
if q.collection_exists(COLLECTION): q.delete_collection(COLLECTION)
q.create_collection(COLLECTION, vectors_config=VectorParams(size=1024, distance=Distance.COSINE))
q.create_payload_index(COLLECTION, "vegetarian", PayloadSchemaType.BOOL)
q.create_payload_index(COLLECTION, "cuisine_type", PayloadSchemaType.KEYWORD)

for start in range(0, len(df), BATCH):
    chunk = df.iloc[start:start + BATCH]
    texts = [f"{r.recipe_name}. Ingredients: {', '.join(r.ingredients)}" for r in chunk.itertuples()]
    vecs = ollama.embed(model="bge-m3", input=texts)["embeddings"]
    q.upsert(COLLECTION, points=[PointStruct(
        id=start + i, vector=vecs[i], payload={
            "name": r.recipe_name, "ingredients": r.ingredients,
            "ingredient_lines": r.ingredient_lines, "servings": None if pd.isna(r.servings) else int(r.servings),
            "calories_per_serving": None if pd.isna(r.calories_per_serving) else round(r.calories_per_serving),
            "protein_g": r.protein_g, "carbs_g": r.carbs_g, "fat_g": r.fat_g,
            "vegetarian": bool(r.vegetarian), "vegan": bool(r.vegan),
            "diet_labels": r.diet_labels, "cuisine_type": r.cuisine_type,
            "image_url": r.image_url or None,
        }) for i, r in enumerate(chunk.itertuples())])
    if start % 3200 == 0: print(f"{start}/{len(df)}")
print("done:", len(df))