# scripts/build_ft_data.py
import pandas as pd
import ast
import random
import json

random.seed(42)

df = pd.read_csv("data/RAW_recipes.csv").dropna(subset=["name"]).head(60000)
pairs = []

for _, row in df.iterrows():
    try:
        ingredients = ast.literal_eval(row["ingredients"])
        if len(ingredients) < 3:
            continue
    except:
        continue
    
    recipe_text = f"{row['name']}. Ingredients: {', '.join(ingredients[:15])}"
    
    # Positive: dish name -> recipe
    pairs.append({"query": row["name"], "positive": recipe_text})
    
    # Positive: ingredient subset -> recipe  
    if len(ingredients) >= 4:
        subset = random.sample(ingredients, min(5, len(ingredients)))
        pairs.append({"query": "Ingredients: " + ", ".join(subset), "positive": recipe_text})

# Save
with open("data/ft_pairs.jsonl", "w") as f:
    for p in pairs:
        f.write(json.dumps(p) + "\n")

print(f"Created {len(pairs)} pairs")