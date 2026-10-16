import pandas as pd, ollama, json, re
from qdrant_client import QdrantClient

q = QdrantClient(url="http://localhost:6333")
qs = pd.read_csv("eval/queries.csv")
COLLECTIONS = ["recipes_v4"]          # add others if you want the comparison too
K = 10

STOP = {"the","a","an","with","and","or","for","of","in","on","made","from",
        "without","easy","simple","quick","recipe","best","homemade","style"}

def toks(s):
    return [w for w in re.sub(r"[^a-z\s]", " ", str(s).lower()).split()
            if w not in STOP and len(w) > 2]

def fuzzy_hit(title, expected):
    """Token overlap: catches '3 bean salad' vs 'cold 3 bean salad'."""
    t, e = set(toks(title)), set(toks(expected))
    return bool(t and e) and len(t & e) / len(e) >= 0.6

def llm_judge(query, expected, got_title):
    prompt = (
        "A user searched a recipe database. Decide if the retrieved recipe is an "
        "ACCEPTABLE answer to the query, even if the title differs from the expected one.\n"
        f"Query: {query}\nExpected recipe: {expected}\nRetrieved recipe: {got_title}\n"
        'Answer ONLY JSON: {"acceptable": true, "reason": "max 10 words"}\n'
        "Acceptable = same dish, an obvious variant, or clearly satisfies the query. "
        "Not acceptable = a different dish or unrelated."
    )
    try:
        r = ollama.chat(model="qwen2.5:3b", format="json",
                        options={"temperature": 0},
                        messages=[{"role": "user", "content": prompt}])
        return json.loads(r["message"]["content"]).get("acceptable") is True
    except Exception:
        return False

def run(col):
    strict_r, fuzzy_r, llm_r = [], [], []
    print(f"\n=== {col} — per-query detail ===")
    for _, row in qs.iterrows():
        query, expected = row["query"], row["expected_name"]
        v = ollama.embed(model="bge-m3", input=[query])["embeddings"][0]
        pts = q.query_points(col, query=v, limit=K).points
        titles = [p.payload["name"] for p in pts]

        exp = str(expected).lower()
        strict = next((i+1 for i, t in enumerate(titles) if exp in t.lower()), None)
        fuzzy  = next((i+1 for i, t in enumerate(titles) if fuzzy_hit(t, expected)), None)

        llm = None
        for i, t in enumerate(titles[:5]):
            if llm_judge(query, expected, t):
                llm = i + 1
                break

        strict_r.append(strict); fuzzy_r.append(fuzzy); llm_r.append(llm)
        flag = "" if strict else ("  <- strict miss" if llm else "  <- REAL MISS")
        print(f"  [{str(query)[:38]:38s}] strict={strict} fuzzy={fuzzy} llm={llm}{flag}")

    def report(name, ranks):
        n = len(ranks)
        line = " ".join(f"hit@{k}={sum(r is not None and r <= k for r in ranks)/n:.2f}"
                        for k in (3, 5, K))
        mrr = sum(1.0/r for r in ranks if r) / n
        print(f"{name:8s} {line} MRR={mrr:.2f}")

    print(f"\n=== {col} — {len(qs)} queries, k={K} ===")
    report("strict", strict_r)   # your old metric, for comparison
    report("fuzzy", fuzzy_r)     # token-overlap lenient
    report("llmjudge", llm_r)    # LLM-as-judge lenient

for col in COLLECTIONS:
    if not q.collection_exists(col):
        print(col, "not found, skipped")
        continue
    run(col)