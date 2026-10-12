let o = {};
try { o = JSON.parse($json.message.content); } catch (e) {}
const line = x => typeof x === "string" ? x.trim()
  : [x && x.quantity, x && (x.item || x.name)].filter(Boolean).join(" ").trim();
const ingredients = (Array.isArray(o.ingredients) ? o.ingredients : []).map(line).filter(Boolean);
const steps = (Array.isArray(o.steps) ? o.steps : []).map(s => String(s).trim()).filter(Boolean);
const title = String(o.title || "").trim();
const ok = ingredients.length > 0 || steps.length > 0;
const time = o.time != null ? o.time : (o.time_minutes != null ? o.time_minutes : null);
return [{ json: {
  mode: "document", source: "photo",
  query: ok ? (title || "recipe from document") : "",
  user_ingredients: [], uncertain: [],
  parsed: { title, servings: o.servings != null ? o.servings : null, time, ingredients, steps }
} }];
