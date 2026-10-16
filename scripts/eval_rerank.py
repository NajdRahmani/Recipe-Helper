"""Dish-name retrieval the way the workflow does it: vector search, then rerank by name overlap.
eval.py measures plain vector search only; the workflow also reranks (node "Rank recipes").
Usage: python scripts/eval_rerank.py [collection]      (default: recipes_rich)
Run from the project root; needs Qdrant and Ollama running."""
import sys
from ranker import toks


def name_rerank(hits, query):
    """Same rule as the 'Rank recipes' node for dish and text inputs: fraction of query words found in the
    recipe name (stemmed, words longer than 2 letters), ties broken by the vector score."""
    qt = sorted({t for t in toks(query) if len(t) > 2})

    def score(h):
        name_t = toks(h["name"])
        return sum(1 for t in qt if t in name_t) / len(qt) if qt else 0.0

    return sorted(hits, key=lambda h: (-score(h), -h["score"]))


def metrics(ranked_lists, expected):
    res = {}
    n = len(expected)
    for k in (1, 3, 5, 10):
        res[f"hit@{k}"] = sum(1 for r, e in zip(ranked_lists, expected) if e in [h["name"] for h in r[:k]]) / n
    rr = 0.0
    for r, e in zip(ranked_lists, expected):
        names = [h["name"] for h in r[:10]]
        if e in names:
            rr += 1 / (names.index(e) + 1)
    res["MRR"] = rr / n
    return res


def main():
    import pandas as pd
    import ollama
    from qdrant_client import QdrantClient

    collection = sys.argv[1] if len(sys.argv) > 1 else "recipes_v4"
    q = QdrantClient(url="http://localhost:6333")
    qs = pd.read_csv("eval/queries.csv")
    expected = [str(e).strip() for e in qs["expected_name"]]

    pools = []
    for query in qs["query"]:
        v = ollama.embed(model="bge-m3", input=[query])["embeddings"][0]
        pts = q.query_points(collection, query=v, limit=30, with_payload=True).points
        pools.append([{"name": p.payload["name"].strip(), "score": p.score} for p in pts])

    variants = {
        "vector top-10 (eval.py)": [p[:10] for p in pools],
        "top-10 + name rerank (the workflow)": [name_rerank(p[:10], qq) for p, qq in zip(pools, qs["query"])],
        "top-30 + name rerank (bigger pool)": [name_rerank(p, qq) for p, qq in zip(pools, qs["query"])],
    }
    print(f"collection: {collection}, {len(expected)} queries")
    for name, ranked in variants.items():
        m = metrics(ranked, expected)
        print(f"  {name:38s} " + " ".join(f"{k}={v:.2f}" for k, v in m.items()))

    print("\nMisses of the workflow variant (check whether the top results are acceptable near-duplicates):")
    for ranked, e, qq in zip(variants["top-10 + name rerank (the workflow)"], expected, qs["query"]):
        if e not in [h["name"] for h in ranked[:10]]:
            print(f"- query: {qq}\n    expected: {e}\n    got: " + " | ".join(h["name"] for h in ranked[:3]))


if __name__ == "__main__":
    main()
