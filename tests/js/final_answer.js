const r = $('Rank recipes').first().json;
const chef = $('Parse chef').first().json.chef;
let verdicts = [];
try { verdicts = JSON.parse($json.message.content).verdicts || []; } catch (e) {}
let subs = chef.substitutions;
if (Array.isArray(verdicts) && verdicts.length === subs.length) subs = subs.filter((s, i) => verdicts[i] !== false);

const c = r.chosen;
if (!c) return [{ json: { answer: "I could not find a matching recipe in the knowledge base. Try other ingredients or a different dish name." } }];
const cap = s => { s = String(s).trim(); return s.charAt(0).toUpperCase() + s.slice(1); };

const head = [cap(c.name) + " (" + c.minutes + " min)"];
if (chef.intro) head.push(chef.intro);
head.push("");
if (r.mode === "ingredients") {
  head.push((r.source === "photo" ? "Detected in your photo: " : "Your ingredients: ") + r.user_ingredients.join(", "));
  if (r.uncertain.length) head.push("Not sure about (ignored): " + [...new Set(r.uncertain)].join(", "));
  head.push("");
  head.push("You have (" + c.have.length + " of " + c.needed.length + "): " + (c.have.join(", ") || "-"));
  head.push(c.missing.length ? "Missing (" + c.missing.length + "): " + c.missing.join(", ") : "You have everything you need!");
  if (c.pantry.length) head.push("Pantry basics: " + c.pantry.join(", "));
  if (subs.length) { head.push(""); head.push("Substitutions:"); subs.forEach(s => head.push("- " + s.missing + " -> " + s.replace_with)); }
} else {
  head.push("Ingredients needed: " + c.needed.concat(c.pantry).join(", "));
}
head.push("");
const foot = [];
if (r.mode === "ingredients" && r.alternatives.length) {
  foot.push("");
  foot.push("Other close options: " + r.alternatives.map(a => cap(a.name) + " (missing " + a.missing + ")").join("; "));
}
if (chef.tip) { foot.push(""); foot.push("Tip: " + chef.tip); }
const steps = (c.steps || []).slice(0, 12).map((s, i) => (i + 1) + ". " + cap(s));
const build = () => head.concat(["Steps:"], steps, foot).join("\n");
let out = build();
while (out.length > 3900 && steps.length > 3) { steps.pop(); out = build(); }
out = out.replace(/[*_`\[\]]/g, "");
if (out.length > 4000) out = out.slice(0, 3990) + "...";
return [{ json: { answer: out, mode: r.mode, chosen: c.name, missing: c.missing.length, rule_substitutions_kept: subs.length } }];
