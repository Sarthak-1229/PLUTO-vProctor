"""Focused probe v2: dump the REAL nested traces the AIML layer emits live,
using the correct field names (_selection.search.*, adaptation.phase_after/
ability_after). Confirms named search algorithms fire (not just argmin fallback)
and the REBUILD-easier invariant holds against the live server."""
import json
import urllib.request

BASE = "http://127.0.0.1:8080"


def _req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


resume = ("Application security engineer: penetration testing, SIEM, incident "
          "response, threat modeling, OWASP, cryptography, SOC, malware analysis.")
start = _req("POST", "/interview/start",
             {"resume_text": resume, "filename": "r.txt", "limit": 12,
              "consent": {"audio": True, "store_transcript": True}})
sid = start["session_id"]
print(f"session={sid}  role={start['target_role']}  pool={start['pool_size']}")

WEAK = "Um, I am not really sure. Maybe something like that, I think, honestly not certain."
algos_seen = set()
anchor_b = None
rebuild_checks = []
print("-" * 78)
print(f"{'#':<3}{'qid':<12}{'cat':<22}{'b':<3}{'algo':<9}{'phase':<9}{'chosen_b':<9}{'fb':<3}")
for turn in range(1, 8):
    nxt = _req("GET", f"/interview/next?session_id={sid}")
    if nxt.get("done"):
        print(f"{turn:<3}(pool exhausted)")
        break
    q = nxt["question"]
    sr = (q.get("_selection") or {}).get("search") or {}
    algo = sr.get("algorithm", "-")
    algos_seen.add(algo)
    cb = sr.get("chosen_b")
    ph = sr.get("phase", "-")
    fb = sr.get("fallback")
    print(f"{turn:<3}{q['id']:<12}{q.get('category','?'):<22}{q.get('difficulty','?'):<3}"
          f"{algo:<9}{ph:<9}{str(cb):<9}{str(fb):<3}")
    if ph == "rebuild" and anchor_b is not None and cb is not None:
        rebuild_checks.append((cb, anchor_b, cb < anchor_b))
    anchor_b = cb if cb is not None else anchor_b
    ans = _req("POST", "/interview/answer",
               {"session_id": sid, "question_id": q["id"], "transcript": WEAK,
                "delivery": {"fps": 12}})
    a = ans["adaptation"]
    print(f"     S={a['content_score']:<8} ability {a['ability_before']} -> {a['ability_after']}"
          f"   phase {a['phase_before']} -> {a['phase_after']}")
    print(f"       note: {a['phase_note']}")

print("-" * 78)
print(f"search algorithms that fired live : {sorted(algos_seen)}")
print(f"REBUILD 'strictly easier' checks   : "
      f"{rebuild_checks if rebuild_checks else '(no rebuild turn captured)'}")
ok = all(c[2] for c in rebuild_checks) if rebuild_checks else True
named = algos_seen - {"argmin", "none", "-"}
print(f"named (non-fallback) search used   : {sorted(named) if named else 'NONE — all argmin fallback'}")
print(f"invariant (rebuild picks easier)   : {'HOLDS' if ok else 'VIOLATED'}")
