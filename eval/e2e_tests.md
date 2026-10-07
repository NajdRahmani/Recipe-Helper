# End-to-end tests

Terminal-only E2E runs use the same Ollama, Qdrant, prompts, normalization, and pass criteria as the n8n workflow.

| # | Input | Expected | Output summary | Pass/Fail | Cause |
|---|-------|----------|----------------|-----------|-------|
| 1 | Text: chicken pasta | Grounded recipe answer | retrieval=5 | Pass |  |
| 2 | Text: vegetarian chili | Grounded recipe answer | retrieval=5 | Pass |  |
| 3 | Text: quick chocolate dessert | Grounded recipe answer | retrieval=5 | Pass |  |
| 4 | Image: dish_01.jpeg | Grounded recipe answer | retrieval=5 | Pass |  |
| 5 | Image: dish_02.webp | Grounded recipe answer | retrieval=5 | Pass |  |
| 6 | Image: dish_03.jpg | Grounded recipe answer | retrieval=5 | Pass |  |
| 7 | Image: doc_01.png | Grounded recipe answer | retrieval=5 | Pass |  |
| 8 | Image: doc_02.png | Grounded recipe answer | retrieval=5 | Pass |  |
| 9 | Image: doc_03.png | Grounded recipe answer | retrieval=5 | Pass |  |
| 10 | Image: ing_01.png | Grounded recipe answer | retrieval=5 | Pass |  |
| 11 | Image: ing_02.jpg | Grounded recipe answer | retrieval=5 | Pass |  |
| 12 | Image: ing_03.jpg | Grounded recipe answer | retrieval=5 | Pass |  |
| 13 | Image: ing_04.jpeg | Grounded recipe answer | retrieval=5 | Pass |  |
| 14 | Image: ing_05.jpeg | Grounded recipe answer | retrieval=5 | Pass |  |
| 15 | Image: ing_06.jpeg | Grounded recipe answer | retrieval=5 | Pass |  |
| 16 | Image: ing_07.jpeg | Grounded recipe answer | retrieval=5 | Pass |  |

v1 text/multimodal pass rate: 16/16 (100%)


v2 pass rate: not applicable. The initial document failures were caused by a harness normalization mismatch, not model prompts; after fixing the harness, all 16 cases passed.
