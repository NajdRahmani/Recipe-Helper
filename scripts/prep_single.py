import pandas as pd

df = pd.read_parquet("data/recipes_clean.parquet")

# --- Auto-detect units: sodium %DV is usually >5, sodium grams usually <3 ---
sodium_median = df["sodium"].median()
is_pct_dv = sodium_median > 5
print(f"sodium median = {sodium_median} -> treating macros as {'%DV (converting)' if is_pct_dv else 'grams (already converted)'}")

# FDA daily values, 2000 kcal diet
DV = {"fat": 70.0, "protein": 50.0, "carbs": 275.0}

if is_pct_dv:
    df["kcal"]      = df["calories"].round(1)
    df["fat_g"]     = (df["total_fat"] / 100 * DV["fat"]).round(1)
    df["protein_g"] = (df["protein"]   / 100 * DV["protein"]).round(1)
    df["carbs_g"]   = (df["carbs"]     / 100 * DV["carbs"]).round(1)
else:
    df["kcal"]      = df["calories"].round(1)
    df["fat_g"]     = df["total_fat"].round(1)
    df["protein_g"] = df["protein"].round(1)
    df["carbs_g"]   = df["carbs"].round(1)

# dataset-2 fields stay empty on purpose (photo node will skip silently)
for col in ["image_url", "ingredient_lines", "cuisine"]:
    if col not in df.columns:
        df[col] = None
# --- data-quality filter: drop implausible per-serving values ---
bad = (df["kcal"] > 3000) | (df["carbs_g"] > 300) | (df["fat_g"] > 200) | (df["kcal"] <= 0)
print(f"dropping {bad.sum()} implausible rows ({bad.mean():.2%})")
df = df[~bad].reset_index(drop=True)

df.to_parquet("data/recipes_single.parquet")

print(df[["name", "kcal", "fat_g", "protein_g", "carbs_g"]].head(10))
print("coverage:", df["kcal"].notna().sum(), "/", len(df), "rows")