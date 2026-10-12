const fs = require("fs");
const run = (file, json, nodes = {}) => {
  const code = fs.readFileSync("js/" + file, "utf8");
  const $ = name => ({ first: () => ({ json: nodes[name] }) });
  const fn = new Function("$json", "$", code);
  return fn(json, $)[0].json;
};
const trig = { message: { text: "x", caption: "vegetarian 30 min please", chat: { id: 1 } } };
const ollama = obj => ({ message: { content: JSON.stringify(obj) } });
let ok = 0, fail = 0;
const t = (name, cond, extra) => { if (cond) { ok++; } else { fail++; console.log("FAIL", name, extra || ""); } };

// router
t("router doc", run("parse_router.js", ollama({ type: "recipe_document", confidence: 0.9 })).type === "recipe_document");
t("router bad", run("parse_router.js", { message: { content: "garbage" } }).type === "ingredients_photo");
t("router dish", run("parse_router.js", ollama({ type: "Dish_Photo" })).type === "dish_photo");

// normalize 1
let n1 = run("normalize_ingredients.js", ollama({ ingredients: [{ name: "Chicken", confidence: 0.9 }, { name: "chicken", confidence: 0.8 }, { name: "rice", confidence: 0.4 }, { name: "Onion", confidence: 0.7 }], uncertain: ["cheese"] }), { "Telegram Trigger": trig });
t("n1 ing", JSON.stringify(n1.user_ingredients) === '["chicken","onion"]', JSON.stringify(n1));
t("n1 dropped", n1.uncertain.includes("rice") && n1.uncertain.includes("cheese"));
t("n1 caption", n1.max_minutes === 30 && n1.vegetarian === true);
t("n1 query", n1.query === "Ingredients: chicken, onion");
let n1e = run("normalize_ingredients.js", ollama({ ingredients: [] }), { "Telegram Trigger": { message: {} } });
t("n1 empty", n1e.query === "");

// normalize 2
t("n2", run("normalize_dish.js", ollama({ dish: "Lasagna", likely_ingredients: ["beef"] })).user_ingredients.length === 0);
t("n2 query", run("normalize_dish.js", ollama({ dish: "Lasagna" })).query === "lasagna");

// normalize 3
let n3 = run("normalize_document.js", ollama({ title: "Crepes", ingredients: ["200 g flour", { item: "eggs", quantity: "2" }], steps: ["Mix", "Cook"], time_minutes: 20 }));
t("n3", n3.parsed.ingredients[1] === "2 eggs" && n3.query === "Crepes" && n3.parsed.time === 20, JSON.stringify(n3));
t("n3 empty", run("normalize_document.js", ollama({})).query === "");

// normalize text
const tt = (raw, o) => run("normalize_text.js", ollama(o), { "Telegram Trigger": { message: { text: raw } } });
t("nt ing", tt("I have eggs and tomatoes", { intent: "ingredients", items: ["Eggs", "tomatoes"] }).mode === "ingredients");
t("nt dish", tt("lasagna under 40 minutes", { intent: "dish", dish: "lasagna", max_minutes: 40 }).max_minutes === 40);
t("nt cmd", tt("/start", {}).query === "");
t("nt bad", tt("pizza", null || {}).query === "pizza");

// rank
const mk = (name, ings, score, minutes = 30) => ({ score, payload: { name, minutes, ingredients: ings, steps: ["do it", "then do that", "serve"] } });
const results = [
  mk("chicken rice bake", ["chicken breasts", "rice", "onion", "cheddar cheese", "cream of mushroom soup", "salt", "pepper"], 0.80),
  mk("simple chicken rice", ["chicken", "rice", "onion", "garlic", "salt", "water", "olive oil"], 0.70),
  mk("chicken tikka", ["chicken", "yogurt", "garam masala", "ginger", "garlic", "lemon juice", "tomato paste", "salt"], 0.75),
  mk("plain rice", ["rice", "water", "salt"], 0.60),
  mk("onion soup", ["onions", "beef broth", "bread", "gruyere cheese", "butter"], 0.65),
];
const q = { mode: "ingredients", user_ingredients: ["chicken", "rice", "onion", "garlic"], query: "Ingredients: chicken, rice, onion, garlic", uncertain: [], source: "photo" };
let rk = run("rank.js", { result: results }, { "Has query": q });
t("rank best", rk.chosen.name === "simple chicken rice", JSON.stringify(rk.chosen));
t("rank missing", rk.chosen.missing.length === 0, JSON.stringify(rk.chosen.missing));
t("rank pantry", rk.chosen.pantry.includes("salt") && rk.chosen.pantry.includes("water") && rk.chosen.pantry.includes("olive oil"));
t("rank alts", rk.alternatives.length === 2);
t("rank excludes trivial", rk.chosen.name !== "plain rice");
// dish mode name boost
let rd = run("rank.js", { result: results }, { "Has query": { mode: "dish", user_ingredients: [], query: "chicken tikka", uncertain: [] } });
t("dish pick", rd.chosen.name === "chicken tikka" && rd.chosen.have.length === 0 && rd.chosen.missing.length === 0, JSON.stringify(rd.chosen));
// plural/stem matching
let rs = run("rank.js", { result: [mk("tomato egg", ["tomatoes", "eggs", "scallions", "salt"], 0.9)] }, { "Has query": { mode: "ingredients", user_ingredients: ["tomato", "egg"], query: "x", uncertain: [] } });
t("stem", rs.chosen.have.length === 2 && rs.chosen.missing.length === 1, JSON.stringify(rs.chosen));
// empty
t("rank empty", run("rank.js", { result: [] }, { "Has query": q }).chosen === null);

// parse chef
const rankOut = rk;
let pc = run("parse_chef.js", ollama({ intro: "A *nice* dish", substitutions: [{ missing: "x", replace_with: "y" }, { missing: "Garlic", replace_with: "garlic powder" }], tip: "Stir" }), { "Rank recipes": { chosen: { missing: ["garlic"] } } });
t("parse chef", pc.chef.substitutions.length === 1 && pc.chef.intro === "A nice dish", JSON.stringify(pc));

// final answer
const fin = run("final_answer.js", ollama({ verdicts: [true] }), { "Rank recipes": rk, "Parse chef": { chef: { intro: "Easy.", tip: "Rest it.", substitutions: [{ missing: "x", replace_with: "y" }] } } });
console.log("\n--- FINAL (ingredients) ---\n" + fin.answer);
const rkDish = rd;
const fin2 = run("final_answer.js", ollama({ verdicts: [] }), { "Rank recipes": rkDish, "Parse chef": { chef: { intro: "Spicy.", tip: "Marinate.", substitutions: [] } } });
console.log("\n--- FINAL (dish) ---\n" + fin2.answer);
t("dish no have/missing", !/You have|Missing/.test(fin2.answer));
const fin3 = run("document_answer.js", { parsed: n3.parsed });
console.log("\n--- DOC ---\n" + fin3.answer);
t("doc no have/missing", !/You have|Missing/.test(fin3.answer));
console.log(`\n${ok} passed, ${fail} failed`);
