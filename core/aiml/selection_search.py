"""
Search-based question selection for PLUTO vProctor (MDM AIML, requirement 3+6).

Formalizes "pick the next question / ask a similar easier one / change domain"
as classic graph search over a per-session QUESTION GRAPH:

  nodes  = the session's pool questions (attrs: difficulty b, fine category,
           coarse domain bucket, KMeans sub-topic cluster)
  edges  = a difficulty LADDER (same category, adjacent tier) + sub-topic
           AFFINITY links (same KMeans cluster) so related items connect

Named algorithms implemented + used (all uninformed/informed classical search):
  A*                 f = g(path/coverage cost) + h(|b - b_target|)   MEASURE/SWITCH
  Greedy Best-First  h only (compared against A* in the experiments module)
  BFS / Depth-Limited nearest strictly-EASIER same-domain node        REBUILD
  Iterative Deepening escalate to a harder node on a high streak       ESCALATE
  Bidirectional      path between two questions (transition explanation)

The engine hook is feature-flagged (AIML_SEARCH_ENABLED); with it off, adaptive.py
uses its original nearest-by-difficulty scheduler. Selection ALWAYS falls back to
argmin|b - b_target| over the allowed set, so the pool is fully served regardless.
"""
from __future__ import annotations

import heapq
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from core.aiml import flag


def _bucket(cat: str) -> str:
    """Coarse domain bucket. Mirrors core.interview.adaptive.topic_of (kept local
    to avoid an import cycle: adaptive imports this module)."""
    if cat == "behavioral":
        return "behavioral"
    if cat == "hr_culture":
        return "hr"
    if cat == "situational":
        return "situational"
    return "technical"


def _b(q: dict) -> float:
    return float((q.get("irt") or {}).get("b", 1300))

@dataclass
class QuestionGraph:
    nodes: Dict[str, dict]              # qid -> {b, cat, bucket, cluster}
    adj: Dict[str, Set[str]]           # qid -> neighbor qids
    order: List[str] = field(default_factory=list)

    @classmethod
    def build(cls, qids: List[str], bank, tm=None) -> "QuestionGraph":
        nodes: Dict[str, dict] = {}
        for qid in qids:
            q = bank.get(qid)
            if not q:
                continue
            cat = q.get("category", "?")
            nodes[qid] = {"b": _b(q), "cat": cat, "bucket": _bucket(cat),
                          "cluster": tm.cluster_of(qid) if tm else -1}
        adj: Dict[str, Set[str]] = {qid: set() for qid in nodes}

        # 1) difficulty-ladder edges: same fine category, adjacent tier level.
        by_cat: Dict[str, List[str]] = {}
        for qid, n in nodes.items():
            by_cat.setdefault(n["cat"], []).append(qid)
        for cat_ids in by_cat.values():
            levels = sorted({nodes[i]["b"] for i in cat_ids})
            rank = {b: r for r, b in enumerate(levels)}
            for a in cat_ids:
                for b in cat_ids:
                    if a != b and abs(rank[nodes[a]["b"]] - rank[nodes[b]["b"]]) == 1:
                        adj[a].add(b)
                        adj[b].add(a)

        # 2) sub-topic affinity edges: same KMeans cluster (may bridge domains).
        by_cl: Dict[int, List[str]] = {}
        for qid, n in nodes.items():
            if n["cluster"] >= 0:
                by_cl.setdefault(n["cluster"], []).append(qid)
        for cl_ids in by_cl.values():
            for i in range(len(cl_ids)):
                for j in range(i + 1, len(cl_ids)):
                    adj[cl_ids[i]].add(cl_ids[j])
                    adj[cl_ids[j]].add(cl_ids[i])

        return cls(nodes=nodes, adj=adj, order=list(nodes.keys()))

# ---- uninformed search ----------------------------------------------------
GoalFn = Callable[[str], bool]


def bfs(graph: QuestionGraph, start: str, goal_fn: GoalFn) -> Tuple[Optional[str], List[str]]:
    """Breadth-first: shortest edge path from start to the nearest goal node."""
    if start not in graph.nodes:
        return None, []
    q = deque([[start]])
    seen = {start}
    while q:
        path = q.popleft()
        node = path[-1]
        if node != start and goal_fn(node):
            return node, path
        for nb in sorted(graph.adj.get(node, ())):
            if nb not in seen:
                seen.add(nb)
                q.append(path + [nb])
    return None, []


def dls(graph: QuestionGraph, start: str, goal_fn: GoalFn,
        limit: int) -> Tuple[Optional[str], List[str]]:
    """Depth-limited DFS: nearest goal within `limit` edges of start."""
    def rec(node: str, path: List[str], depth: int):
        if node != start and goal_fn(node):
            return node, path
        if depth >= limit:
            return None, None
        for nb in sorted(graph.adj.get(node, ())):
            if nb not in path:
                g, p = rec(nb, path + [nb], depth + 1)
                if g:
                    return g, p
        return None, None
    if start not in graph.nodes:
        return None, []
    g, p = rec(start, [start], 0)
    return (g, p) if g else (None, [])


def ids(graph: QuestionGraph, start: str, goal_fn: GoalFn,
        max_depth: int = 6) -> Tuple[Optional[str], List[str]]:
    """Iterative deepening: DLS with a growing limit (BFS-optimal, DFS-cheap)."""
    for depth in range(1, max_depth + 1):
        g, p = dls(graph, start, goal_fn, depth)
        if g:
            return g, p
    return None, []

# ---- informed / heuristic search ------------------------------------------
Heuristic = Callable[[str], float]
EdgeCost = Callable[[str, str], float]


def greedy_best_first(graph: QuestionGraph, start: str, goal_fn: GoalFn,
                      h: Heuristic) -> Tuple[Optional[str], List[str]]:
    """Greedy Best-First: expand the frontier node with the smallest h alone."""
    if start not in graph.nodes:
        return None, []
    cnt = 0
    pq = [(h(start), cnt, start, [start])]
    seen: Set[str] = set()
    while pq:
        _, _, node, path = heapq.heappop(pq)
        if node in seen:
            continue
        seen.add(node)
        if node != start and goal_fn(node):
            return node, path
        for nb in graph.adj.get(node, ()):
            if nb not in seen:
                cnt += 1
                heapq.heappush(pq, (h(nb), cnt, nb, path + [nb]))
    return None, []


def astar(graph: QuestionGraph, start: str, goal_fn: GoalFn,
          h: Heuristic, edge_cost: EdgeCost) -> Tuple[Optional[str], List[str]]:
    """A*: expand by f = g (accumulated edge cost) + h (difficulty distance)."""
    if start not in graph.nodes:
        return None, []
    cnt = 0
    pq = [(h(start), 0.0, cnt, start, [start])]
    best: Dict[str, float] = {start: 0.0}
    while pq:
        _, g, _, node, path = heapq.heappop(pq)
        if node != start and goal_fn(node):
            return node, path
        if g > best.get(node, float("inf")):
            continue
        for nb in graph.adj.get(node, ()):
            ng = g + edge_cost(node, nb)
            if ng < best.get(nb, float("inf")):
                best[nb] = ng
                cnt += 1
                heapq.heappush(pq, (ng + h(nb), ng, cnt, nb, path + [nb]))
    return None, []


def bidirectional(graph: QuestionGraph, start: str, goal: str) -> List[str]:
    """Bidirectional BFS: shortest path between two specific questions (used to
    explain a transition, e.g. why the engine moved from item A to item B)."""
    if start not in graph.nodes or goal not in graph.nodes:
        return []
    if start == goal:
        return [start]
    fparent: Dict[str, Optional[str]] = {start: None}
    bparent: Dict[str, Optional[str]] = {goal: None}
    fq, bq = deque([start]), deque([goal])
    meet: Optional[str] = None
    while fq and bq and meet is None:
        for _ in range(len(fq)):
            node = fq.popleft()
            for nb in sorted(graph.adj.get(node, ())):
                if nb not in fparent:
                    fparent[nb] = node
                    fq.append(nb)
                    if nb in bparent:
                        meet = nb
                        break
            if meet:
                break
        if meet:
            break
        for _ in range(len(bq)):
            node = bq.popleft()
            for nb in sorted(graph.adj.get(node, ())):
                if nb not in bparent:
                    bparent[nb] = node
                    bq.append(nb)
                    if nb in fparent:
                        meet = nb
                        break
            if meet:
                break
    if meet is None:
        return []
    left: List[str] = []
    x: Optional[str] = meet
    while x is not None:
        left.append(x)
        x = fparent[x]
    left.reverse()
    right: List[str] = []
    x = bparent[meet]
    while x is not None:
        right.append(x)
        x = bparent[x]
    return left + right

# ---- selection dispatcher -------------------------------------------------
REBUILD_MARGIN = 40.0     # a candidate must be this much EASIER to count as "easier"
ESCALATE_MARGIN = 40.0    # ...HARDER, to count as an escalation
TARGET_BAND = 80.0        # A* goal band: within this |b - b_target| of the target
IDS_MAX_DEPTH = 6


def _nearest(cands: List[str], keyfn) -> Optional[str]:
    return min(cands, key=keyfn) if cands else None


class SelectionSearch:
    """Pick the next question id INSIDE an already-chosen coarse bucket by running
    a NAMED classical search from the last-asked (anchor) node over the session
    QUESTION GRAPH, then fall back to argmin|b - b_target| so the pool is always
    fully served (preserves adaptive.py's full-serve invariant)."""

    def __init__(self, tm=None):
        self._tm = tm

    def _topic_model(self):
        if self._tm is not None:
            return self._tm
        try:
            from core.aiml.topics import get_topic_model
            return get_topic_model()
        except Exception:
            return None

    def select(self, bank, candidate_ids: List[str], b_target: float,
               phase: str = "measure", anchor_id: Optional[str] = None):
        cands = [c for c in candidate_ids if bank.get(c)]
        if not cands:
            return None, {"algorithm": "none", "reason": "empty-candidates"}
        phase = (phase or "measure").lower()
        graph = QuestionGraph.build(
            list(set(cands + ([anchor_id] if anchor_id else []))),
            bank, self._topic_model())
        cand_set = set(cands)

        def bval(x: str) -> float:
            return graph.nodes[x]["b"] if x in graph.nodes else _b(bank.get(x) or {})

        h = lambda x: abs(bval(x) - b_target)
        anchor_ok = bool(anchor_id) and anchor_id in graph.nodes
        anchor_b = bval(anchor_id) if anchor_ok else b_target
        anchor_bucket = graph.nodes[anchor_id]["bucket"] if anchor_ok else None

        # Named search by FSM phase (all from the anchor node over the graph):
        #   REBUILD  -> BFS/DLS to the nearest strictly-EASIER same-domain node
        #   ESCALATE -> IDS to a strictly-HARDER node (escalate on a high streak)
        #   MEASURE/SWITCH/default -> A* (g=hops, h=|b - b_target|), Greedy backup
        goal_qid, path, algo = None, [], "argmin"
        if anchor_ok:
            if phase == "rebuild":
                gf = (lambda x: x in cand_set
                      and graph.nodes[x]["bucket"] == anchor_bucket
                      and bval(x) < anchor_b - REBUILD_MARGIN)
                goal_qid, path = bfs(graph, anchor_id, gf)
                algo = "BFS"
                if goal_qid is None:
                    goal_qid, path = dls(graph, anchor_id, gf, IDS_MAX_DEPTH)
                    algo = "DLS"
            elif phase == "escalate":
                gf = lambda x: x in cand_set and bval(x) > anchor_b + ESCALATE_MARGIN
                goal_qid, path = ids(graph, anchor_id, gf, IDS_MAX_DEPTH)
                algo = "IDS"
            else:  # measure / switch / anything else
                gf = lambda x: x in cand_set and h(x) <= TARGET_BAND
                goal_qid, path = astar(graph, anchor_id, gf, h, lambda a, b: 1.0)
                algo = "A*"
                if goal_qid is None:
                    goal_qid, path = greedy_best_first(graph, anchor_id, gf, h)
                    algo = "Greedy"

        if goal_qid is not None and goal_qid in cand_set:
            return goal_qid, {"algorithm": algo, "phase": phase,
                              "anchor": anchor_id, "b_target": round(b_target, 1),
                              "path": path, "chosen_b": round(bval(goal_qid), 1),
                              "fallback": False}

        # ---- argmin fallback: guarantees a pick so the full pool stays served ---
        if phase == "rebuild" and anchor_ok:
            pool = ([c for c in cands
                     if graph.nodes.get(c, {}).get("bucket") == anchor_bucket
                     and bval(c) < anchor_b - REBUILD_MARGIN]
                    or [c for c in cands if bval(c) < anchor_b] or cands)
        elif phase == "escalate" and anchor_ok:
            pool = ([c for c in cands if bval(c) > anchor_b + ESCALATE_MARGIN]
                    or [c for c in cands if bval(c) > anchor_b] or cands)
        else:
            pool = cands
        pick = _nearest(pool, h)
        return pick, {"algorithm": "argmin", "phase": phase, "anchor": anchor_id,
                      "b_target": round(b_target, 1),
                      "chosen_b": round(bval(pick), 1), "fallback": True,
                      "searched": algo if anchor_ok else "no-anchor"}


_SINGLETON: Optional[SelectionSearch] = None


def get_selection_search() -> Optional[SelectionSearch]:
    """Lazy singleton. None when AIML_SEARCH_ENABLED is off, so adaptive.py
    transparently falls back to its Elo/FSM nearest-by-difficulty scheduler."""
    global _SINGLETON
    if not flag("AIML_SEARCH_ENABLED", True):
        return None
    if _SINGLETON is None:
        _SINGLETON = SelectionSearch()
    return _SINGLETON


if __name__ == "__main__":
    from core.interview.question_bank import get_question_bank
    bank = get_question_bank()
    tech = [q["id"] for q in bank.all_questions()
            if q.get("category", "").startswith("tech_")][:40]
    ss = SelectionSearch()
    for ph in ("measure", "rebuild", "escalate"):
        anchor = tech[len(tech) // 2]
        qid, tr = ss.select(bank, [c for c in tech if c != anchor],
                            b_target=1300, phase=ph, anchor_id=anchor)
        print(f"{ph:<9} anchor={anchor} -> {qid}  {tr['algorithm']} "
              f"(fallback={tr['fallback']}, chosen_b={tr['chosen_b']})")





