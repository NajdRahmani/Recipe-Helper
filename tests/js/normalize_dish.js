let o = {};
try { o = JSON.parse($json.message.content); } catch (e) {}
const dish = String(o.dish || "").toLowerCase().trim();
return [{ json: { mode: "dish", source: "photo", query: dish, user_ingredients: [], uncertain: [], max_minutes: null, vegetarian: false } }];
