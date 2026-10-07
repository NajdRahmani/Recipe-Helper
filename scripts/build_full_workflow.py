import copy
import json
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "workflows" / "recipe-helper.json"
target = ROOT / "workflows" / "recipe-helper-full.json"
workflow = json.loads(source.read_text())[0]
base_names = {"Recipe Helper", "Input Type", "Image to base64", "Router", "Parse router", "Code in JavaScript"}
nodes = [node for node in workflow["nodes"] if node["name"] in base_names]
for node in nodes:
    if node["name"] == "Code in JavaScript":
        node["name"] = "Parse router"

workflow["nodes"] = nodes
workflow["connections"] = {
    "Recipe Helper": {"main": [[{"node": "Input Type", "type": "main", "index": 0}]]},
    "Input Type": {"main": [[{"node": "Image to base64", "type": "main", "index": 0}], []]},
    "Image to base64": {"main": [[{"node": "Router", "type": "main", "index": 0}]]},
    "Router": {"main": [[{"node": "Parse router", "type": "main", "index": 0}]]},
}

form_trigger = next(node for node in nodes if node["name"] == "Recipe Helper")
form_trigger["parameters"].setdefault("options", {})["respondWhen"] = "responseNode"
form_trigger["parameters"]["formFields"]["values"] = [
    {"fieldLabel": "image", "fieldType": "file", "requiredField": False},
    {"fieldLabel": "message", "requiredField": False},
]

for node in nodes:
    if node["type"] == "n8n-nodes-base.httpRequest":
        node["parameters"]["method"] = "POST"
        node["parameters"].setdefault("options", {})["timeout"] = 300000
        node["retryOnFail"] = True
        node["maxTries"] = 3


def node_id():
    return str(uuid.uuid4())


def add(name, node_type, parameters, position, version=2):
    node = {
        "parameters": parameters,
        "type": node_type,
        "typeVersion": version,
        "position": position,
        "id": node_id(),
        "name": name,
    }
    nodes.append(node)
    return node


def http(name, body, position, url="http://host.docker.internal:11434/api/chat"):
    if body.startswith("{{"):
        body = "=" + body
    node = add(
        name,
        "n8n-nodes-base.httpRequest",
        {
            "method": "POST",
            "url": url,
            "authentication": "none",
            "sendBody": True,
            "contentType": "json",
            "specifyBody": "json",
            "jsonBody": body,
            "options": {"timeout": 300000},
        },
        position,
        4.5,
    )
    node["retryOnFail"] = True
    node["maxTries"] = 3
    return node


def code(name, source_code, position):
    return add(
        name,
        "n8n-nodes-base.code",
        {"mode": "runOnceForAllItems", "jsCode": source_code},
        position,
        2,
    )


router = next(node for node in nodes if node["name"] == "Router")
input_type = next(node for node in nodes if node["name"] == "Input Type")


route = add(
    "Route by type",
    "n8n-nodes-base.switch",
    {
        "rules": {
            "values": [
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 3}, "conditions": [{"leftValue": "={{ $json.type }}", "rightValue": "ingredients_photo", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "renameOutput": True, "outputKey": "ingredients"},
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 3}, "conditions": [{"leftValue": "={{ $json.type }}", "rightValue": "dish_photo", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "renameOutput": True, "outputKey": "dish"},
                {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 3}, "conditions": [{"leftValue": "={{ $json.type }}", "rightValue": "recipe_document", "operator": {"type": "string", "operation": "equals"}}], "combinator": "and"}, "renameOutput": True, "outputKey": "document"},
            ]
        },
        "options": {"fallbackOutput": "extra"},
    },
    [900, -120],
    3.4,
)

vision_ingredients = http("Vision ingredients", '{{ JSON.stringify({ model: "gemma3:4b", stream: false, format: "json", messages: [ { role: "system", content: "You identify food ingredients in a photo. Return ONLY JSON: {\\"ingredients\\": [{\\"name\\": string, \\"confidence\\": number}], \\"uncertain\\": [string]}. List only clearly visible items." }, { role: "user", content: "List the ingredients.", images: [ $(\'Image to base64\').first().json.b64 ] } ] }) }}', [1160, -220])
vision_dish = http("Vision dish", '{{ JSON.stringify({ model: "gemma3:4b", stream: false, format: "json", messages: [ { role: "system", content: "Identify the cooked dish. Return ONLY JSON: {\\"dish\\": string, \\"likely_ingredients\\": [string]}." }, { role: "user", content: "What dish is this?", images: [ $(\'Image to base64\').first().json.b64 ] } ] }) }}', [1160, -80])
recipe_parser = http("Recipe parser", '{{ JSON.stringify({ model: "gemma3:4b", stream: false, format: "json", messages: [ { role: "system", content: "Extract only the written recipe. Return ONLY JSON with title, servings, time_minutes, ingredients, and steps. Never invent missing quantities or steps." }, { role: "user", content: "Extract the recipe.", images: [ $(\'Image to base64\').first().json.b64 ] } ] }) }}', [1160, 60])

normalize_code = '''let o = {};
try { o = JSON.parse($json.message.content); } catch (e) {}
let ing = [], query = "";
if (Array.isArray(o.ingredients) && o.ingredients.length && o.ingredients[0].name !== undefined) {
  ing = o.ingredients.filter(i => i.confidence >= 0.6).map(i => i.name);
  query = ing.length ? "recipe using " + ing.join(", ") : "";
} else if (o.dish) {
  ing = o.likely_ingredients || [];
  query = o.dish + " recipe";
} else if (o.title) {
  ing = (o.ingredients || []).map(i => i.item);
  query = o.title + " " + ing.join(", ");
}
return [{ json: { query, user_ingredients: ing } }];'''

normalize_1 = code("Normalize 1", normalize_code, [1400, -220])
normalize_2 = code("Normalize 2", normalize_code, [1400, -80])
normalize_3 = code("Normalize 3", normalize_code, [1400, 60])
normalize_text = code("Normalize text", 'return [{ json: { query: $json.message || "", user_ingredients: [] } }];', [500, 180])

has_query = add("Has query", "n8n-nodes-base.if", {"conditions": {"options": {"caseSensitive": True, "typeValidation": "strict", "version": 2}, "conditions": [{"leftValue": "={{ $json.query }}", "rightValue": "", "operator": {"type": "string", "operation": "notEmpty"}}], "combinator": "and"}}, [1650, 0], 2.2)
empty = add("Nothing found", "n8n-nodes-base.form", {"operation": "completion", "completionTitle": "Nothing found", "completionMessage": "I could not detect any ingredients or request. Please try a clearer photo or type your question."}, [1880, 140], 1)
embed = http("Embed query", '{{ JSON.stringify({ model: "bge-m3", input: $json.query }) }}', [1880, -40], "http://host.docker.internal:11434/api/embed")
rag = http("RAG search", '{{ JSON.stringify({ vector: $json.embeddings[0], limit: 5, with_payload: true }) }}', [2120, -40], "http://qdrant:6333/collections/recipes_fixed/points/search")
has_results = add("Has results", "n8n-nodes-base.if", {"conditions": {"options": {"caseSensitive": True, "typeValidation": "strict", "version": 2}, "conditions": [{"leftValue": "={{ $json.result.length }}", "rightValue": 0, "operator": {"type": "number", "operation": "gt"}}], "combinator": "and"}}, [2360, -40], 2.2)
no_match = add("No match", "n8n-nodes-base.form", {"operation": "completion", "completionTitle": "No match", "completionMessage": "No matching recipe was found in the knowledge base."}, [2600, 100], 1)
context = code("Build context", 'const ctx = $json.result.map(h => h.payload.text).join("\\n\\n---\\n\\n");\nconst n = $(\'Has query\').first().json;\nreturn [{ json: { context: ctx, query: n.query, user_ingredients: n.user_ingredients } }];', [2600, -40])

chef = http("Chef", '{{ JSON.stringify({ model: "gemma3:4b", stream: false, messages: [ { role: "system", content: "You are a helpful home chef. Use ONLY the provided recipes. Answer with best matching recipe, time, HAVE vs MISSING ingredients, substitutions, and numbered steps." }, { role: "user", content: "User request: " + $json.query + "\\nUser ingredients: " + $json.user_ingredients.join(", ") + "\\n\\nCandidate recipes:\\n" + $json.context } ] }) }}', [2840, -40])
validator = http("Validator", '{{ JSON.stringify({ model: "qwen2.5:3b", stream: false, format: "json", messages: [ { role: "system", content: "Return ONLY JSON: {\\"valid\\": boolean, \\"issues\\": [string]}. Check HAVE ingredients, non-empty steps, and context grounding." }, { role: "user", content: "User ingredients: " + $(\'Build context\').first().json.user_ingredients.join(", ") + "\\n\\nContext:\\n" + $(\'Build context\').first().json.context + "\\n\\nAnswer:\\n" + $json.message.content } ] }) }}', [3080, -40])
final_answer = code("Final answer", 'const chef = $(\'Chef\').first().json.message.content;\nlet v = { valid: true, issues: [] };\ntry { v = JSON.parse($json.message.content); } catch (e) {}\nconst note = v.valid ? "" : "\\n\\nValidator warnings: " + (v.issues || []).join("; ");\nreturn [{ json: { answer: chef + note } }];', [3320, -40])
output = add("Your recipe", "n8n-nodes-base.form", {"operation": "completion", "completionTitle": "Your recipe", "completionMessage": "={{ $json.answer }}"}, [3560, -40], 1)


connections = workflow["connections"]
connections["Router"] = {"main": [[{"node": "Parse router", "type": "main", "index": 0}]]}
connections["Parse router"] = {"main": [[{"node": "Route by type", "type": "main", "index": 0}]]}
connections["Route by type"] = {"main": [[{"node": "Vision ingredients", "type": "main", "index": 0}], [{"node": "Vision dish", "type": "main", "index": 0}], [{"node": "Recipe parser", "type": "main", "index": 0}], [{"node": "Vision ingredients", "type": "main", "index": 0}]]}
connections["Vision ingredients"] = {"main": [[{"node": "Normalize 1", "type": "main", "index": 0}]]}
connections["Vision dish"] = {"main": [[{"node": "Normalize 2", "type": "main", "index": 0}]]}
connections["Recipe parser"] = {"main": [[{"node": "Normalize 3", "type": "main", "index": 0}]]}
connections["Input Type"]["main"].append([{"node": "Normalize text", "type": "main", "index": 0}])
connections["Normalize 1"] = {"main": [[{"node": "Has query", "type": "main", "index": 0}]]}
connections["Normalize 2"] = {"main": [[{"node": "Has query", "type": "main", "index": 0}]]}
connections["Normalize 3"] = {"main": [[{"node": "Has query", "type": "main", "index": 0}]]}
connections["Normalize text"] = {"main": [[{"node": "Has query", "type": "main", "index": 0}]]}
connections["Has query"] = {"main": [[{"node": "Embed query", "type": "main", "index": 0}], [{"node": "Nothing found", "type": "main", "index": 0}]]}
connections["Embed query"] = {"main": [[{"node": "RAG search", "type": "main", "index": 0}]]}
connections["RAG search"] = {"main": [[{"node": "Has results", "type": "main", "index": 0}]]}
connections["Has results"] = {"main": [[{"node": "Build context", "type": "main", "index": 0}], [{"node": "No match", "type": "main", "index": 0}]]}
connections["Build context"] = {"main": [[{"node": "Chef", "type": "main", "index": 0}]]}
connections["Chef"] = {"main": [[{"node": "Validator", "type": "main", "index": 0}]]}
connections["Validator"] = {"main": [[{"node": "Final answer", "type": "main", "index": 0}]]}
connections["Final answer"] = {"main": [[{"node": "Your recipe", "type": "main", "index": 0}]]}

workflow["name"] = "recipe-helper-full"
workflow["id"] = "859164a4-5c6f-429d-8147-17eeee31fdc4"
workflow["active"] = False
target.write_text(json.dumps([workflow], indent=2))
print(target)