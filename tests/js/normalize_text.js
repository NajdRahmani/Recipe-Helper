const raw = ((($('Telegram Trigger').first().json.message || {}).text) || "").trim();
let o = {};
try { o = JSON.parse($json.message.content); } catch (e) {}
if (!raw || raw.startsWith("/")) {
  return [{ json: { mode: "text", source: "text", query: "", user_ingredients: [], uncertain: [] } }];
}
const items = [...new Set((Array.isArray(o.items) ? o.items : [])
  .map(x => String(x).toLowerCase().trim()).filter(Boolean))];
const maxMin = Number(o.max_minutes) > 0 ? Number(o.max_minutes) : null;
const veg = o.vegetarian === true;
if (o.intent === "ingredients" && items.length) {
  return [{ json: { mode: "ingredients", source: "text", query: "Ingredients: " + items.join(", "),
    user_ingredients: items, uncertain: [], max_minutes: maxMin, vegetarian: veg } }];
}
const dish = ((o.dish && String(o.dish).trim()) || raw).toLowerCase();
return [{ json: { mode: "text", source: "text", query: dish, user_ingredients: [], uncertain: [],
  max_minutes: maxMin, vegetarian: veg } }];
