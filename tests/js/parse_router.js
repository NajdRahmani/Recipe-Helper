let o = {};
try { o = JSON.parse($json.message.content); } catch (e) {}
const t = String(o.type || "").toLowerCase();
const type = t.includes("document") || t.includes("recipe") ? "recipe_document"
  : t.includes("dish") ? "dish_photo" : "ingredients_photo";
return [{ json: { type, confidence: Number(o.confidence) || 0 } }];
