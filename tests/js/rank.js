const n = $('Has query').first().json;
const hits = ($json.result || []).filter(h => h.payload && Array.isArray(h.payload.ingredients));

const STAPLES = ["salt", "pepper", "black pepper", "white pepper", "water", "hot water", "warm water",
  "cold water", "boiling water", "oil", "vegetable oil", "olive oil", "cooking oil", "cooking spray",
  "sugar", "ice", "ice cubes", "kosher salt", "sea salt", "salt and pepper"];
const stem = w => {
  if (w.length <= 3) return w;
  if (w.endsWith("ies")) return w.slice(0, -3) + "y";
  if (w.endsWith("oes")) return w.slice(0, -2);
  if (w.endsWith("ss")) return w;
  if (w.endsWith("s")) return w.slice(0, -1);
  return w;
};
const toks = s => String(s).toLowerCase().replace(/[^a-z\s]/g, " ").split(/\s+/).filter(Boolean).map(stem);
const STAPLE_KEYS = new Set(STAPLES.map(s => toks(s).join(" ")));
const isStaple = r => STAPLE_KEYS.has(toks(r).join(" "));

const user = (n.user_ingredients || []).map(u => toks(u)).filter(t => t.length);
const matches = (r, u) => {
  const R = toks(r);
  return u.every(t => R.includes(t)) || R.every(t => u.includes(t));
};
const analyse = h => {
  const pantry = [], needed = [];
  h.payload.ingredients.forEach(r => (isStaple(r) ? pantry : needed).push(r));
  const have = needed.filter(r => user.some(u => matches(r, u)));
  const missing = needed.filter(r => !user.some(u => matches(r, u)));
  const usedUser = user.filter(u => needed.some(r => matches(r, u))).length;
  return { h, pantry, needed, have, missing, usedUser };
};
const pack = a => ({
  name: a.h.payload.name, minutes: a.h.payload.minutes, steps: a.h.payload.steps || [],
  pantry: a.pantry, needed: a.needed, have: a.have, missing: a.missing, score: a.h.score
});

let ranked = [];
if (n.mode === "ingredients" && user.length) {
  const all = hits.map(analyse);
  const minUsed = Math.min(2, user.length);
  let pool = all.filter(a => a.usedUser >= minUsed && a.needed.length >= 3);
  if (!pool.length) pool = all.filter(a => a.usedUser >= 1);
  if (!pool.length) pool = all;
  ranked = pool.sort((a, b) => (a.missing.length - b.missing.length)
    || (b.usedUser - a.usedUser) || ((b.h.score || 0) - (a.h.score || 0)));
} else {
  const qt = [...new Set(toks(n.query).filter(t => t.length > 2))];
  const nameScore = a => qt.length ? qt.filter(t => toks(a.h.payload.name).includes(t)).length / qt.length : 0;
  ranked = hits.map(analyse).sort((a, b) => (nameScore(b) - nameScore(a)) || ((b.h.score || 0) - (a.h.score || 0)));
  ranked.forEach(a => { a.have = []; a.missing = []; });
}
const chosen = ranked.length ? pack(ranked[0]) : null;
const alternatives = ranked.slice(1, 3).map(a => ({ name: a.h.payload.name, missing: a.missing.length, minutes: a.h.payload.minutes }));
return [{ json: {
  mode: n.mode, source: n.source || "", query: n.query,
  user_ingredients: n.user_ingredients || [], uncertain: n.uncertain || [],
  chosen, alternatives, retrieved: hits.length
} }];
