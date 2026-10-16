# scripts/ft_bge.py
import json
import torch
from sentence_transformers import SentenceTransformer, InputExample, losses
from torch.utils.data import DataLoader

model = SentenceTransformer("BAAI/bge-m3")
model.max_seq_length = 512

# Load pairs
examples = []
with open("data/ft_pairs.jsonl") as f:
    for line in f:
        d = json.loads(line)
        examples.append(InputExample(texts=[d["query"], d["positive"]]))

# In-batch negatives: other positives in batch become negatives
train_loss = losses.MultipleNegativesRankingLoss(model)
train_dataloader = DataLoader(examples, shuffle=True, batch_size=32)

model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=1,  # Start with 1 epoch, ~2-3 hours on CPU
    warmup_steps=100,
    optimizer_params={"lr": 2e-5},
    output_path="models/bge-ft",
    show_progress_bar=True
)