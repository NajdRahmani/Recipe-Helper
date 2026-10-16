# scripts/rerank_service.py
from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import CrossEncoder
import uvicorn

app = FastAPI()
model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

class Req(BaseModel):
    query: str
    candidates: list
    top_k: int = 5

@app.post("/rerank")
def rerank(req: Req):
    pairs = [[req.query, f"{c['name']}. Ingredients: {', '.join(c.get('ingredients', [])[:10])}"] 
             for c in req.candidates]
    scores = model.predict(pairs)
    
    for c, s in zip(req.candidates, scores):
        c["rerank_score"] = float(s)
    
    return sorted(req.candidates, key=lambda x: x["rerank_score"], reverse=True)[:req.top_k]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)