"""
CSP + metaheuristic pool assembly for PLUTO vProctor (MDM AIML, requirement 1+2+6).

Casts "assemble the interview question POOL from a résumé" as a Constraint
Satisfaction Problem, then optimizes the feasible pool with two classic
metaheuristics — the syllabus algorithms doing real work:

  CSP (backtracking + forward-checking)   build a pool meeting every HARD
                                          constraint: size, category quotas,
                                          uniqueness, a minimum difficulty spread
  Local Search (hill climbing)            swap items to climb a SOFT-objective
                                          fitness (résumé coverage + diversity)
  Genetic Algorithm                       population / crossover / mutation search
                                          over feasible pools for a better optimum

Hard constraints come from question_bank.DEFAULT_QUOTAS; the soft fitness rewards
résumé-skill coverage, role fit and category/difficulty diversity and penalizes
tag redundancy. Feature-flagged (AIML_CSP_ENABLED); with it off (or on any error)
question_bank.select_for_resume falls back to its greedy quota selector, so the
pool is always assembled.
"""
from __future__ import annotations

import random
from collections import Counter
from typing import Dict, List, Optional, Tuple

from core.aiml import flag

RANDOM_SEED = 13
MIN_TIERS = 3            # pool must span >= this many difficulty tiers (hard)
GA_POP, GA_GENS = 24, 40
LS_STEPS = 200
STEP_CAP = 20000        # backtracking safety valve -> greedy fallback if exceeded

_TIERS = [1000, 1150, 1300, 1450, 1600]


def _b(q: dict) -> float:
    return float((q.get("irt") or {}).get("b", 1300))


def _cat(q: dict) -> str:
    return q.get("category", "?")


def _tags(q: dict) -> set:
    return set(q.get("tags", []) or [])


def _role_hit(q: dict, role: str) -> float:
    rf = q.get("role_fit", [])
    return 1.0 if (role in rf or "*" in rf) else 0.0


def _tier(q: dict) -> int:
    b = _b(q)
    return min(range(len(_TIERS)), key=lambda i: abs(_TIERS[i] - b)) + 1


def _score(q: dict, rtags: set, role: str) -> float:
    """Candidate ordering score (mirrors question_bank._score, self-contained)."""
    qt = _tags(q)
    overlap = len(rtags & qt) / max(1, len(qt)) if qt else 0.0
    return 1.0 * _role_hit(q, role) + 0.6 * overlap


def _fitness(pool: List[dict], rtags: set, role: str) -> float:
    """Soft objective the metaheuristics maximize (hard constraints already met)."""
    if not pool:
        return 0.0
    covered = set()
    for q in pool:
        covered |= (_tags(q) & rtags)
    coverage = len(covered) / len(rtags) if rtags else 0.0
    role_fit = sum(_role_hit(q, role) for q in pool) / len(pool)
    cats = {_cat(q) for q in pool}
    tiers = {_tier(q) for q in pool}
    diversity = 0.5 * (len(cats) / max(1, min(len(pool), 8))) + 0.5 * (len(tiers) / 5.0)
    all_tags = [t for q in pool for t in _tags(q)]
    redundancy = (len(all_tags) - len(set(all_tags))) / max(1, len(all_tags))
    return round(1.0 * coverage + 0.6 * role_fit + 0.5 * diversity - 0.3 * redundancy, 4)

# ---- CSP: backtracking + forward-checking ---------------------------------
def _clamp_quotas(cands: List[dict], quotas: Dict[str, int]) -> Dict[str, int]:
    """Never demand more of a category than the bank actually offers."""
    avail = Counter(_cat(q) for q in cands)
    return {c: min(n, avail.get(c, 0)) for c, n in quotas.items()}


def csp_build(order: List[dict], limit: int,
              quotas: Dict[str, int]) -> Optional[Tuple[List[dict], int]]:
    """Backtracking search for a pool of exactly `limit` questions that meets the
    category quotas, uniqueness and the difficulty-spread constraint.

    `order` is tried front-to-back, so a score-descending order yields a high-
    score first solution. Forward-checking prunes: after each choice we verify
    the still-unmet quota deficits can *still* be filled from the remaining
    candidates within the remaining slots. Returns (pool, steps) or None.
    """
    limit = min(limit, len(order))
    quotas = _clamp_quotas(order, quotas)
    tier_target = min(MIN_TIERS, limit, len({_tier(q) for q in order}))
    chosen: List[dict] = []
    chosen_ids: set = set()
    cat_count: Counter = Counter()
    steps = [0]

    def bt(idx: int) -> bool:
        steps[0] += 1
        if len(chosen) == limit:
            if any(cat_count.get(c, 0) < quotas[c] for c in quotas):
                return False                          # quota not met -> reject
            return len({_tier(q) for q in chosen}) >= tier_target
        if idx >= len(order) or steps[0] > STEP_CAP:
            return False
        slots_left = limit - len(chosen)
        rem = order[idx:]
        rem_cat = Counter(_cat(q) for q in rem if q["id"] not in chosen_ids)
        deficit = {c: max(0, quotas[c] - cat_count.get(c, 0)) for c in quotas}
        if sum(deficit.values()) > slots_left:
            return False
        for c, d in deficit.items():
            if d > rem_cat.get(c, 0):
                return False
        q = order[idx]
        if q["id"] not in chosen_ids:                 # branch 1: take q
            chosen.append(q)
            chosen_ids.add(q["id"])
            cat_count[_cat(q)] += 1
            if bt(idx + 1):
                return True
            chosen.pop()
            chosen_ids.discard(q["id"])
            cat_count[_cat(q)] -= 1
        return bt(idx + 1)                             # branch 2: skip q

    if limit == 0 or not order:
        return ([], 0)
    return (list(chosen), steps[0]) if bt(0) else None

# ---- repair + Local Search (hill climbing) --------------------------------
def _repair(pref_ids: List[str], by_id: Dict[str, dict], base_order: List[dict],
            limit: int, quotas: Dict[str, int]) -> Optional[List[dict]]:
    """Turn any (possibly infeasible) list of ids into a feasible pool by
    re-running the CSP with a biased order: the preferred items are tried first,
    then the rest of the score-ordered candidates fill/repair the constraints."""
    seen: set = set()
    pref: List[dict] = []
    for i in pref_ids:
        if i in by_id and i not in seen:
            seen.add(i)
            pref.append(by_id[i])
    rest = [q for q in base_order if q["id"] not in seen]
    res = csp_build(pref + rest, limit, quotas)
    return res[0] if res else None


def local_search(pool: List[dict], by_id: Dict[str, dict], base_order: List[dict],
                 rtags: set, role: str, limit: int, quotas: Dict[str, int],
                 rng: random.Random) -> Tuple[List[dict], int]:
    """Hill climbing: repeatedly promote one non-chosen candidate (dropping one
    chosen item) and keep the repaired pool only if fitness strictly improves."""
    best = pool
    best_fit = _fitness(best, rtags, role)
    chosen_ids = {q["id"] for q in best}
    outside = [q for q in base_order if q["id"] not in chosen_ids]
    improved = 0
    for _ in range(LS_STEPS):
        if not best or not outside:
            break
        drop = rng.choice(best)
        promote = rng.choice(outside)
        pref = [promote["id"]] + [q["id"] for q in best if q["id"] != drop["id"]]
        cand = _repair(pref, by_id, base_order, limit, quotas)
        if cand is None:
            continue
        fit = _fitness(cand, rtags, role)
        if fit > best_fit:
            best, best_fit = cand, fit
            chosen_ids = {q["id"] for q in best}
            outside = [q for q in base_order if q["id"] not in chosen_ids]
            improved += 1
    return best, improved

# ---- Genetic Algorithm ----------------------------------------------------
def genetic_algorithm(seed_pool: List[dict], by_id: Dict[str, dict],
                      base_order: List[dict], rtags: set, role: str,
                      limit: int, quotas: Dict[str, int],
                      rng: random.Random) -> Tuple[List[dict], Dict]:
    """Population/crossover/mutation search over FEASIBLE pools. Every genome is
    kept feasible by _repair (which re-solves the CSP), so the GA only ever
    optimizes the soft fitness — it can never violate a quota or the size."""
    all_ids = [q["id"] for q in base_order]

    def random_pool() -> List[dict]:
        pref = rng.sample(all_ids, min(len(all_ids), limit))
        return _repair(pref, by_id, base_order, limit, quotas) or seed_pool

    def fit(p: List[dict]) -> float:
        return _fitness(p, rtags, role)

    pop = [seed_pool] + [random_pool() for _ in range(GA_POP - 1)]
    best = max(pop, key=fit)
    gen_best = fit(best)

    def tournament() -> List[dict]:
        a, b = rng.choice(pop), rng.choice(pop)
        return a if fit(a) >= fit(b) else b

    for _ in range(GA_GENS):
        nxt = [best]                                   # elitism
        while len(nxt) < GA_POP:
            pa, pb = tournament(), tournament()
            mix = [q["id"] for q in pa] + [q["id"] for q in pb]
            rng.shuffle(mix)                           # crossover: recombine ids
            child = _repair(mix, by_id, base_order, limit, quotas)
            if child is None:
                child = random_pool()
            elif rng.random() < 0.3:                   # mutation: promote one item
                promote = rng.choice(all_ids)
                pref = [promote] + [q["id"] for q in child]
                child = _repair(pref, by_id, base_order, limit, quotas) or child
            nxt.append(child)
        pop = nxt
        cur = max(pop, key=fit)
        if fit(cur) > gen_best:
            best, gen_best = cur, fit(cur)
    return best, {"pop": GA_POP, "gens": GA_GENS, "fitness": round(gen_best, 4)}

# ---- orchestration + runtime hook -----------------------------------------
class CSPSelector:
    """Assemble a résumé-grounded pool: CSP feasibility -> Local Search -> GA."""

    def select(self, candidates: List[dict], target_role: str = "*",
               resume_tags: Optional[List[str]] = None, limit: int = 15,
               quotas: Optional[Dict[str, int]] = None
               ) -> Optional[Tuple[List[str], Dict]]:
        if not candidates:
            return None
        rtags = set(resume_tags or [])
        quotas = dict(quotas or {})
        base_order = sorted(candidates,
                            key=lambda q: (_score(q, rtags, target_role), q["id"]),
                            reverse=True)
        by_id = {q["id"]: q for q in base_order}

        built = csp_build(base_order, limit, quotas)
        if built is None:
            return None                                 # infeasible -> greedy fallback
        csp_pool, steps = built
        fit_csp = _fitness(csp_pool, rtags, target_role)

        rng = random.Random(RANDOM_SEED)
        ls_pool, improved = local_search(csp_pool, by_id, base_order, rtags,
                                         target_role, limit, quotas, rng)
        fit_ls = _fitness(ls_pool, rtags, target_role)

        ga_pool, ga_info = genetic_algorithm(ls_pool, by_id, base_order, rtags,
                                             target_role, limit, quotas, rng)
        candidates_final = [(csp_pool, fit_csp), (ls_pool, fit_ls),
                            (ga_pool, ga_info["fitness"])]
        best_pool, best_fit = max(candidates_final, key=lambda t: t[1])
        cat_count = Counter(_cat(q) for q in best_pool)
        trace = {
            "method": "CSP(backtrack+forward-check)+LocalSearch+GA",
            "csp_steps": steps, "ls_improved": improved,
            "fitness": {"csp": fit_csp, "local_search": fit_ls,
                        "genetic": ga_info["fitness"], "final": best_fit},
            "pool_size": len(best_pool), "tiers": sorted({_tier(q) for q in best_pool}),
            "categories": dict(cat_count),
        }
        return [q["id"] for q in best_pool], trace


_SINGLETON: Optional[CSPSelector] = None


def get_csp_selector() -> Optional[CSPSelector]:
    """Lazy singleton. None when AIML_CSP_ENABLED is off -> greedy fallback."""
    global _SINGLETON
    if not flag("AIML_CSP_ENABLED", True):
        return None
    if _SINGLETON is None:
        _SINGLETON = CSPSelector()
    return _SINGLETON


if __name__ == "__main__":
    from core.interview.question_bank import DEFAULT_QUOTAS, get_question_bank
    bank = get_question_bank()
    sel = CSPSelector()
    ids, tr = sel.select(bank.all_questions(), target_role="backend_engineer",
                         resume_tags=["python", "sql", "docker", "aws"],
                         limit=15, quotas=DEFAULT_QUOTAS)
    print(f"pool={len(ids)} cats={tr['categories']} tiers={tr['tiers']}")
    print(f"fitness csp={tr['fitness']['csp']} ls={tr['fitness']['local_search']} "
          f"ga={tr['fitness']['genetic']} final={tr['fitness']['final']} "
          f"(csp_steps={tr['csp_steps']}, ls_improved={tr['ls_improved']})")




