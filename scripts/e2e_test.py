import base64
import json
import mimetypes
import re
from pathlib import Path

import ollama
from qdrant_client import QdrantClient


ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = ROOT / "eval" / "images"
RUN_DIR = ROOT / "eval" / "runs"
SUMMARY = ROOT / "eval" / "e2e_tests.md"
COLLECTION = "recipes_fixed"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

ROUTER_PROMPT = (
    'You classify input for a recipe assistant. Return ONLY JSON: '
    '{"type": "ingredients_photo" | "dish_photo" | "recipe_document", '
    '"confidence": number between 0 and 1}. ingredients_photo = raw food items '
    '(fridge, counter, shelf, groceries). dish_photo = a cooked or plated dish. '
    'recipe_document = a page or screenshot containing written recipe text.'
)
VISION_INGREDIENTS_PROMPT = (
    'You identify food ingredients in a photo. Return ONLY JSON: '
    '{"ingredients": [{"name": string, "confidence": number between 0 and 1}], '
    '"uncertain": [string]}. Rules: list only items you can clearly see. Never '
    'guess hidden items. If unsure, put the item in uncertain. Use singular English names.'
)
VISION_DISH_PROMPT = (
    'You identify a cooked dish in a photo. Return ONLY JSON: '
    '{"dish": string, "likely_ingredients": [string]}. Give your single best guess.'
)
RECIPE_PARSER_PROMPT = (
    'Extract the recipe from this image. Return ONLY JSON: {"title": string, '
    '"servings": number or null, "time_minutes": number or null, "ingredients": '
    '[{"item": string, "quantity": string or null}], "steps": [string]}. Copy only '
    'what is written. Use null for missing fields. Never invent quantities or steps.'
)
CHEF_PROMPT = (
    'You are a helpful home chef. You receive the user request and candidate recipes. '
    'Think privately, then answer with: 1) Best matching recipe (title, time) 2) '
    'Ingredients the user HAS vs MISSING 3) Substitutions for missing items 4) Numbered '
    'steps. Use ONLY the provided recipes. Be concise.'
)
VALIDATOR_PROMPT = (
    'You verify a recipe answer. Return ONLY JSON: {"valid": boolean, "issues": [string]}. '
    'Check: every ingredient listed as HAVE appears in the user ingredient list, steps '
    'are not empty, and the answer does not invent a recipe absent from the context.'
)


def parse_json(content):
    try:
        return json.loads(content), None
    except (TypeError, json.JSONDecodeError) as exc:
        return None, str(exc)


def chat_json(system, user, images=None):
    message = {"role": "user", "content": user}
    if images:
        message["images"] = images
    response = ollama.chat(
        model="gemma3:4b",
        format="json",
        messages=[{"role": "system", "content": system}, message],
    )
    value, error = parse_json(response["message"]["content"])
    return value, error, response["message"]["content"]


def normalize(value):
    ingredients = []
    query = ""
    image_ingredients = value.get("ingredients")
    if (
        isinstance(image_ingredients, list)
        and image_ingredients
        and isinstance(image_ingredients[0], dict)
        and "name" in image_ingredients[0]
    ):
        ingredients = [
            item["name"]
            for item in image_ingredients
            if item.get("confidence", 0) >= 0.6
        ]
        query = "recipe using " + ", ".join(ingredients) if ingredients else ""
    elif value.get("dish"):
        ingredients = value.get("likely_ingredients") or []
        query = value["dish"] + " recipe"
    elif value.get("title"):
        ingredients = [
            item.get("item", "")
            for item in value.get("ingredients", [])
            if isinstance(item, dict) and item.get("item")
        ]
        query = value["title"] + " " + ", ".join(ingredients)
    return query, ingredients


def retrieve(query, qdrant):
    vector = ollama.embed(model="bge-m3", input=[query])["embeddings"][0]
    return qdrant.query_points(COLLECTION, query=vector, limit=5, with_payload=True).points


def run_case(case_number, label, query, image_path=None):
    qdrant = QdrantClient(url="http://localhost:6333")
    result = {"number": case_number, "input": label, "errors": [], "agents": {}}
    image = None
    if image_path:
        image = base64.b64encode(image_path.read_bytes()).decode("ascii")
        routed, error, raw = chat_json(ROUTER_PROMPT, "Classify this image.", [image])
        result["agents"]["router"] = {"json": routed, "raw": raw, "error": error}
        if error or not routed or routed.get("type") not in {"ingredients_photo", "dish_photo", "recipe_document"}:
            result["errors"].append("Router did not return valid JSON")
        route_type = routed.get("type") if routed else "ingredients_photo"
        prompts = {
            "ingredients_photo": ("vision_ingredients", VISION_INGREDIENTS_PROMPT, "List the ingredients."),
            "dish_photo": ("vision_dish", VISION_DISH_PROMPT, "What dish is this?"),
            "recipe_document": ("recipe_parser", RECIPE_PARSER_PROMPT, "Extract the recipe."),
        }
        agent_name, prompt, request = prompts.get(route_type, prompts["ingredients_photo"])
        parsed, error, raw = chat_json(prompt, request, [image])
        result["agents"][agent_name] = {"json": parsed, "raw": raw, "error": error}
        if error or parsed is None:
            result["errors"].append(f"{agent_name} did not return valid JSON")
        query, ingredients = normalize(parsed or {})
    else:
        query = query
        ingredients = []
    result["query"] = query
    result["user_ingredients"] = ingredients
    if not query:
        result["errors"].append("Normalization produced an empty query")
        return result

    hits = retrieve(query, qdrant)
    result["retrieval"] = [hit.payload.get("name") for hit in hits]
    if not hits:
        result["errors"].append("No retrieval result")
        return result
    context = "\n\n---\n\n".join(hit.payload.get("text", "") for hit in hits)
    chef = ollama.chat(
        model="gemma3:4b",
        messages=[
            {"role": "system", "content": CHEF_PROMPT},
            {"role": "user", "content": f"User request: {query}\nUser ingredients: {', '.join(ingredients)}\n\nCandidate recipes:\n{context}"},
        ],
    )["message"]["content"]
    result["agents"]["chef"] = chef
    if not re.search(r"\b(HAVE|MISSING)\b", chef, re.IGNORECASE):
        result["errors"].append("Chef answer lacks HAVE/MISSING sections")
    if not re.search(r"(^|\n)\s*1[.)]", chef):
        result["errors"].append("Chef answer lacks numbered steps")

    validator_raw = ollama.chat(
        model="qwen2.5:3b",
        format="json",
        messages=[
            {"role": "system", "content": VALIDATOR_PROMPT},
            {"role": "user", "content": f"User ingredients: {', '.join(ingredients)}\n\nContext:\n{context}\n\nAnswer:\n{chef}"},
        ],
    )["message"]["content"]
    validator, error = parse_json(validator_raw)
    result["agents"]["validator"] = {"json": validator, "raw": validator_raw, "error": error}
    if error or not isinstance(validator, dict) or not isinstance(validator.get("valid"), bool):
        result["errors"].append("Validator did not return valid JSON")
    result["pass"] = not result["errors"]
    return result


def main():
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    cases = [
        ("Text: chicken pasta", "chicken pasta", None),
        ("Text: vegetarian chili", "vegetarian chili", None),
        ("Text: quick chocolate dessert", "quick chocolate dessert", None),
    ]
    for image_path in sorted(IMAGE_DIR.glob("*")) if IMAGE_DIR.exists() else []:
        if image_path.is_file() and image_path.suffix.lower() in IMAGE_SUFFIXES:
            cases.append((f"Image: {image_path.name}", "", image_path))

    rows = []
    for number, (label, query, image_path) in enumerate(cases, 1):
        output = run_case(number, label, query, image_path)
        (RUN_DIR / f"{number:02d}.json").write_text(json.dumps(output, indent=2))
        status = "Pass" if output.get("pass") else "Fail"
        cause = "; ".join(output.get("errors", [])) or ""
        summary = "retrieval=" + str(len(output.get("retrieval", [])))
        rows.append((number, label, "Grounded recipe answer", summary, status, cause))

    image_count = (
        len([p for p in IMAGE_DIR.glob("*") if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES])
        if IMAGE_DIR.exists()
        else 0
    )
    lines = [
        "# End-to-end tests",
        "",
        "Terminal-only E2E runs use the same Ollama, Qdrant, prompts, normalization, and pass criteria as the n8n workflow.",
        "",
        "| # | Input | Expected | Output summary | Pass/Fail | Cause |",
        "|---|-------|----------|----------------|-----------|-------|",
    ]
    lines.extend(f"| {n} | {label} | {expected} | {summary} | {status} | {cause} |" for n, label, expected, summary, status, cause in rows)
    passed = sum(status == "Pass" for *_, status, _ in rows)
    total = len(rows)
    lines.extend([
        "",
        f"v1 text/multimodal pass rate: {passed}/{total} ({passed / total:.0%})" if total else "v1 pass rate: 0/0 (no tests)",
        f"Images discovered: {image_count}. Add 10 ingredient photos, 3 dish photos, and 3 recipe screenshots under `eval/images/` for the full multimodal run." if image_count == 0 else "",
        "",
        "v2 pass rate: pending prompt iteration after observed v1 failures.",
    ])
    SUMMARY.write_text("\n".join(lines) + "\n")
    print(f"completed {total} cases: {passed} passed, {total - passed} failed; images={image_count}")


if __name__ == "__main__":
    main()