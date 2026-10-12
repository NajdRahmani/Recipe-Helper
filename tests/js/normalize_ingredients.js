let o = {};
try { o = JSON.parse($json.message.content); } catch (e) {}
const seen = new Set(), ing = [], dropped = [];
for (const i of (Array.isArray(o.ingredients) ? o.ingredients : [])) {
  const name = String(i && typeof i === "object" ? (i.name || "") : i).toLowerCase().trim();
  if (!name || seen.has(name)) continue;
  seen.add(name);
  const c = i && typeof i === "object" && i.confidence !== undefined ? Number(i.confidence) : 1;
  (c >= 0.6 ? ing : dropped).push(name);
}
const caption = (($('Telegram Trigger').first().json.message || {}).caption || "").toLowerCase();
const m = caption.match(/(\d+)\s*(min|minutes|minute)/);
return [{ json: {
  mode: "ingredients",
  source: "photo",
  query: ing.length ? "Ingredients: " + ing.join(", ") : "",
  user_ingredients: ing,
  uncertain: dropped.concat(Array.isArray(o.uncertain) ? o.uncertain.map(x => String(x).toLowerCase()) : []),
  max_minutes: m ? Number(m[1]) : null,
  vegetarian: /vegetarian|vegan|v[ée]g[ée]tarien/.test(caption)
} }];
