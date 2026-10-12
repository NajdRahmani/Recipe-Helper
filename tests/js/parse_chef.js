const r = $('Rank recipes').first().json;
const c = r.chosen || { missing: [] };
let o = {};
try { o = JSON.parse($json.message.content); } catch (e) {}
const strip = s => String(s || "").replace(/[*_`#\[\]]/g, "").trim();
const missingSet = (c.missing || []).map(m => m.toLowerCase().trim());
const subs = (Array.isArray(o.substitutions) ? o.substitutions : [])
  .filter(s => s && s.missing && s.replace_with && missingSet.includes(String(s.missing).toLowerCase().trim()))
  .slice(0, 3)
  .map(s => ({ missing: strip(s.missing), replace_with: strip(s.replace_with) }));
return [{ json: { chef: { intro: strip(o.intro).slice(0, 220), tip: strip(o.tip).slice(0, 200), substitutions: subs } } }];
