const p = $json.parsed;
const cap = s => { s = String(s).trim(); return s.charAt(0).toUpperCase() + s.slice(1); };
const head = [p.title ? cap(p.title) : "Recipe from your document"];
if (p.servings) head.push("Servings: " + p.servings);
if (p.time) head.push("Time: " + p.time + (/^\d+$/.test(String(p.time)) ? " min" : ""));
head.push("");
head.push("Ingredients needed:");
(p.ingredients.length ? p.ingredients : ["(none detected)"]).forEach(i => head.push("- " + i));
head.push("");
const steps = p.steps.slice(0, 20).map((s, i) => (i + 1) + ". " + cap(s));
const build = () => head.concat(["Steps:"], steps.length ? steps : ["(none detected)"]).join("\n");
let out = build();
while (out.length > 3900 && steps.length > 3) { steps.pop(); out = build(); }
out = out.replace(/[*_`\[\]]/g, "");
if (out.length > 4000) out = out.slice(0, 3990) + "...";
return [{ json: { answer: out, mode: "document" } }];
