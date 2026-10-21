"""Simulated 'user has these ingredients' evaluation: vector top-1 vs vector top-40 + rerank by missing ingredients.
Usage: python scripts/eval_ingredients.py"""
import ast, random
import pandas as pd, ollama
from qdrant_client import QdrantClient
from ranker import analyse, rank, toks

N_CORPUS, N_TESTS, SEED = 2000, 40, 7
q = QdrantClient(url="http://localhost:6333")
df = pd.read_csv("data/RAW_recipes.csv").dropna(subset=["name"]).head(N_CORPUS)
rng = random.Random(SEED)

cases = []
for _, r in df.iterrows():
    ing = ast.literal_eval(r["ingredients"])
    needed = analyse(ing, [])["needed"]
    if len(needed) >= 5:
        cases.append((r["name"].strip(), needed))
rng.shuffle(cases)
cases = cases[:N_TESTS]

def run(holdout):
    base_missing, rer_missing, base_cov, rer_cov = [], [], [], []
    for name, needed in cases:
        k = max(3, round(len(needed) * 0.7))
        user = rng.sample(needed, k)
        v = ollama.embed(model="bge-m3", input=["Ingredients: " + ", ".join(user)])["embeddings"][0]
        pts = q.query_points("recipes_v4", query=v, limit=41, with_payload=True).points
        hits = [(p.score, p.payload) for p in pts if not (holdout and p.payload["name"].strip() == name)][:40]
        if not hits:
            continue
        a0 = analyse(hits[0][1]["ingredients"], user)
        a1 = rank(hits, user)[0][0]
        n_user = len(user)
        base_missing.append(len(a0["missing"])); rer_missing.append(len(a1["missing"]))
        base_cov.append(a0["used"] / n_user); rer_cov.append(a1["used"] / n_user)
    m = lambda x: sum(x) / len(x)
    le2 = lambda x: sum(1 for v in x if v <= 2) / len(x)
    label = "source recipe EXCLUDED (realistic)" if holdout else "source recipe in corpus"
    print(f"\n{label}, {len(base_missing)} cases")
    print(f"  vector top-1      : avg missing {m(base_missing):.2f} | missing<=2: {le2(base_missing):.0%} | user-ingredient coverage {m(base_cov):.0%}")
    print(f"  top-40 + rerank   : avg missing {m(rer_missing):.2f} | missing<=2: {le2(rer_missing):.0%} | user-ingredient coverage {m(rer_cov):.0%}")





run(holdout=True)
run(holdout=False)
