"""Python mirror of the 'Rank recipes' n8n node (js/rank.js). Used only for evaluation."""
STAPLES = ["salt", "pepper", "black pepper", "white pepper", "water", "hot water", "warm water",
           "cold water", "boiling water", "oil", "vegetable oil", "olive oil", "cooking oil",
           "cooking spray", "sugar", "ice", "ice cubes", "kosher salt", "sea salt", "salt and pepper"]


def stem(w):
    if len(w) <= 3:
        return w
    if w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith("oes"):
        return w[:-2]
    if w.endswith("ss"):
        return w
    if w.endswith("s"):
        return w[:-1]
    return w


def toks(s):
    clean = "".join(ch if ("a" <= ch <= "z" or ch == " ") else " " for ch in str(s).lower())
    return [stem(t) for t in clean.split() if t]


STAPLE_KEYS = {" ".join(toks(s)) for s in STAPLES}


def is_staple(r):
    return " ".join(toks(r)) in STAPLE_KEYS


def matches(recipe_ing, user_toks):
    R = toks(recipe_ing)
    return all(t in R for t in user_toks) or all(t in user_toks for t in R)


def analyse(ingredients, user):
    user_toks = [toks(u) for u in user if toks(u)]
    pantry = [r for r in ingredients if is_staple(r)]
    needed = [r for r in ingredients if not is_staple(r)]
    have = [r for r in needed if any(matches(r, u) for u in user_toks)]
    missing = [r for r in needed if not any(matches(r, u) for u in user_toks)]
    used = sum(1 for u in user_toks if any(matches(r, u) for r in needed))
    return {"pantry": pantry, "needed": needed, "have": have, "missing": missing, "used": used}


def rank(hits, user):
    """hits: list of (score, payload). Returns list of (analysis, score, payload) best first."""
    all_ = [(analyse(p["ingredients"], user), s, p) for s, p in hits]
    n_user = len([u for u in user if toks(u)])
    min_used = min(2, n_user)
    pool = [a for a in all_ if a[0]["used"] >= min_used and len(a[0]["needed"]) >= 3]
    if not pool:
        pool = [a for a in all_ if a[0]["used"] >= 1]
    if not pool:
        pool = all_
    return sorted(pool, key=lambda a: (len(a[0]["missing"]), -a[0]["used"], -a[1]))
