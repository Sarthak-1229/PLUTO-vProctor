/* PLUTO vProctor — interview practice front-end.
 *
 * Talks to the JSON API under /interview. Two hard product invariants are
 * respected here as much as on the server:
 *   1. DELIVERY (speech + camera) is DESCRIPTIVE ONLY — we send raw numbers in
 *      `delivery.body`, never a verdict, and never let them influence anything.
 *   2. The answer key is never requested or shown; we only render what the
 *      whitelisted API returns.
 * Everything degrades gracefully: no mic, no camera, or no MediaPipe still lets
 * the user type answers and finish the session.
 */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = {
    sessionId: null, question: null, consent: {},
    answered: false, submitting: false,
  };

  function toast(msg, ms = 2600) {
    const t = $("toast");
    t.textContent = msg; t.classList.add("show");
    clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("show"), ms);
  }

  async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    const res = await fetch(path, opts);
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { detail: text }; }
    if (!res.ok) throw new Error(data.detail || `${res.status} ${res.statusText}`);
    return data;
  }

  function show(name) {
    ["setup", "interview", "report"].forEach((s) =>
      $("screen-" + s).classList.toggle("active", s === name));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ---- Text-to-speech (reuses the existing /speak endpoint) ----------------
  let ttsAudio = null;
  async function speak(text) {
    if (!text) return;
    try {
      const data = await api("POST", "/speak", { text });
      if (data.audio_uri) {
        if (ttsAudio) { ttsAudio.pause(); }
        ttsAudio = new Audio(data.audio_uri);
        ttsAudio.play().catch(() => {});
      }
    } catch (_) { /* TTS is optional; silence on failure */ }
  }

  // ---- Speech-to-text (browser webkitSpeechRecognition; Chrome) -----------
  let recog = null, listening = false, baseTranscript = "";
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

  function ensureRecog() {
    if (recog || !SR) return recog;
    recog = new SR();
    recog.continuous = true; recog.interimResults = true; recog.lang = "en-US";
    recog.onresult = (ev) => {
      let finalTxt = "", interim = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const r = ev.results[i];
        if (r.isFinal) finalTxt += r[0].transcript;
        else interim += r[0].transcript;
      }
      if (finalTxt) baseTranscript = (baseTranscript + " " + finalTxt).trim();
      $("answer").value = (baseTranscript + " " + interim).trim();
    };
    recog.onerror = (ev) => { $("micStatus").textContent = "Mic error: " + ev.error + " — you can type instead."; };
    recog.onend = () => { if (listening) { try { recog.start(); } catch (_) {} } };
    return recog;
  }

  function startMic() {
    if (!state.consent.audio) { toast("Microphone consent not granted."); return; }
    if (!ensureRecog()) { $("micStatus").textContent = "Speech recognition unavailable in this browser — please type."; return; }
    baseTranscript = $("answer").value.trim();
    try { recog.start(); } catch (_) {}
    listening = true;
    $("micBtn").textContent = "◼ stop";
    $("micStatus").innerHTML = '<span class="rec-dot"></span> recording…';
  }
  function stopMic() {
    listening = false;
    if (recog) { try { recog.stop(); } catch (_) {} }
    $("micBtn").textContent = "▶ speak";
    $("micStatus").textContent = "Stopped. Edit the text if needed, then submit.";
  }

  // ---- Camera: DESCRIPTIVE body aggregates, computed in-browser -----------
  // face-present ratio, centered ratio, mean head-motion. Uses MediaPipe's
  // FaceDetector when it loads; if the CDN/model is unavailable we simply skip
  // body metrics (delivery.body stays {}), and the interview is unaffected.
  const MP_URL = "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14";
  let camStream = null, faceDetector = null, camTimer = null, camReady = false;
  let bodyAcc = { samples: 0, faceFrames: 0, centeredFrames: 0, motionSum: 0, moves: 0, lastCx: null, lastCy: null };

  function resetBody() { bodyAcc = { samples: 0, faceFrames: 0, centeredFrames: 0, motionSum: 0, moves: 0, lastCx: null, lastCy: null }; }

  function bodyAggregate() {
    const b = bodyAcc;
    if (!b.samples) return {};
    const r = (x) => Math.round(x * 1000) / 1000;
    const out = {
      samples: b.samples,
      face_present_ratio: r(b.faceFrames / b.samples),
      mean_motion: b.moves ? r(b.motionSum / b.moves) : 0,
    };
    if (b.faceFrames) out.centered_ratio = r(b.centeredFrames / b.faceFrames);
    return out;
  }

  async function startCamera() {
    try {
      camStream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240 }, audio: false });
    } catch (e) { $("camMetrics").textContent = "camera unavailable (" + e.name + ")"; return; }
    const v = $("cam"); v.srcObject = camStream; $("camBox").style.display = "block";
    try {
      const vision = await import(MP_URL + "/vision_bundle.mjs");
      const fileset = await vision.FilesetResolver.forVisionTasks(MP_URL + "/wasm");
      faceDetector = await vision.FaceDetector.createFromOptions(fileset, {
        baseOptions: { modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.tflite" },
        runningMode: "VIDEO",
      });
      camReady = true;
    } catch (e) {
      $("camMetrics").textContent = "live face metrics unavailable — camera on, not analyzed";
    }
    camTimer = setInterval(sampleFrame, 650);
  }

  function sampleFrame() {
    const v = $("cam");
    if (!v || v.readyState < 2) return;
    bodyAcc.samples++;
    if (camReady && faceDetector) {
      try {
        const res = faceDetector.detectForVideo(v, performance.now());
        const det = res && res.detections && res.detections[0];
        if (det && det.boundingBox) {
          const bb = det.boundingBox, W = v.videoWidth || 320, H = v.videoHeight || 240;
          const cx = (bb.originX + bb.width / 2) / W, cy = (bb.originY + bb.height / 2) / H;
          bodyAcc.faceFrames++;
          if (cx > 0.25 && cx < 0.75 && cy > 0.2 && cy < 0.8) bodyAcc.centeredFrames++;
          if (bodyAcc.lastCx !== null) {
            bodyAcc.motionSum += Math.hypot(cx - bodyAcc.lastCx, cy - bodyAcc.lastCy); bodyAcc.moves++;
          }
          bodyAcc.lastCx = cx; bodyAcc.lastCy = cy;
        } else { bodyAcc.lastCx = null; bodyAcc.lastCy = null; }
      } catch (_) {}
      const a = bodyAggregate();
      $("camMetrics").textContent = `face ${Math.round((a.face_present_ratio || 0) * 100)}% · centered ${Math.round((a.centered_ratio || 0) * 100)}% · motion ${a.mean_motion ?? 0} (descriptive)`;
    }
  }

  function stopCamera() {
    if (camTimer) { clearInterval(camTimer); camTimer = null; }
    if (camStream) { camStream.getTracks().forEach((t) => t.stop()); camStream = null; }
    $("camBox").style.display = "none";
  }

  // ---- Setup: parse résumé + start session --------------------------------
  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const rd = new FileReader();
      rd.onload = () => resolve(String(rd.result).split(",", 2)[1] || "");
      rd.onerror = reject; rd.readAsDataURL(file);
    });
  }

  function fillProfile(p) {
    if (!p) return;
    if (p.inferred_role) $("role").value = p.inferred_role;
    if (p.inferred_seniority) $("seniority").value = p.inferred_seniority;
    if (Array.isArray(p.skills)) $("skills").value = p.skills.join(", ");
  }

  async function parseResume() {
    const file = $("resumeFile").files[0];
    const text = $("resumeText").value.trim();
    if (!file && !text) { toast("Add a résumé file or paste text first."); return; }
    $("parseStatus").innerHTML = '<span class="spinner"></span>';
    try {
      const payload = text ? { resume_text: text } : { filename: file.name, content_base64: await fileToBase64(file) };
      const data = await api("POST", "/interview/resume", payload);
      fillProfile(data.profile);
      $("parseStatus").textContent = `Parsed — ${data.pool_size} matching questions found.`;
    } catch (e) {
      $("parseStatus").textContent = "Parse failed: " + e.message;
    }
  }

  async function startInterview() {
    state.consent = { audio: $("cAudio").checked, video: $("cVideo").checked, store_transcript: $("cStore").checked };
    const skills = $("skills").value.split(",").map((s) => s.trim()).filter(Boolean);
    const body = {
      skills, target_role: $("role").value.trim() || "*",
      seniority: $("seniority").value,
      limit: Math.max(3, Math.min(20, parseInt($("limit").value, 10) || 8)),
      consent: state.consent,
    };
    const rt = $("resumeText").value.trim();
    if (!skills.length && rt) body.resume_text = rt;   // let the server infer from text
    $("startStatus").innerHTML = '<span class="spinner"></span>';
    try {
      const data = await api("POST", "/interview/start", body);
      state.sessionId = data.session_id;
      $("startStatus").textContent = "";
      show("interview");
      if (state.consent.video) startCamera();
      await loadNext();
    } catch (e) {
      $("startStatus").textContent = "Could not start: " + e.message;
    }
  }

  // ---- Interview loop -----------------------------------------------------
  function renderQuestion(q, progress) {
    state.question = q; state.answered = false;
    baseTranscript = ""; $("answer").value = "";
    resetBody();
    if (listening) stopMic();
    $("nextBtn").style.display = "none";
    $("submitBtn").style.display = "";
    $("submitBtn").disabled = false;
    $("answerStatus").textContent = "";
    const served = progress ? progress.served : 1, total = progress ? progress.pool_size : 1;
    $("progress").textContent = `Question ${served} of ${total}`;
    $("progressBar").style.width = Math.round((served / Math.max(total, 1)) * 100) + "%";
    const meta = [];
    if (q.category) meta.push(q.category);
    if (q.type) meta.push(q.type);
    if (q.difficulty) meta.push("difficulty " + q.difficulty);
    if (q.expects_star) meta.push("STAR format");
    if (q.expected_answer_seconds) meta.push("~" + q.expected_answer_seconds + "s");
    $("qmeta").innerHTML = meta.map((m) => `<span class="chip">${m}</span>`).join("");
    $("qtext").textContent = q.text || "(no question text)";
    speak(q.text);
  }

  async function loadNext() {
    try {
      const data = await api("GET", "/interview/next?session_id=" + encodeURIComponent(state.sessionId));
      if (data.done) { await showReport(); return; }
      renderQuestion(data.question, data.progress);
    } catch (e) { toast("Failed to load question: " + e.message); }
  }

  async function submitAnswer() {
    if (state.submitting) return;
    if (!state.question) return;
    const transcript = $("answer").value.trim();
    if (!transcript) { toast("Type or speak an answer first (or click Next to skip)."); }
    if (listening) stopMic();
    state.submitting = true;
    $("submitBtn").disabled = true;
    $("answerStatus").innerHTML = '<span class="spinner"></span> grading…';
    const payload = {
      session_id: state.sessionId, question_id: state.question.id,
      transcript, delivery: bodyAggregate(),
    };
    try {
      const data = await api("POST", "/interview/answer", payload);
      state.answered = true;
      const s = data.tier1 ? data.tier1.content_score : null;
      $("answerStatus").textContent = "Recorded" + (s !== null ? ` (content ${(s).toFixed(2)}; refining…)` : "") + ".";
      $("submitBtn").style.display = "none";
      $("nextBtn").style.display = "";
    } catch (e) {
      $("answerStatus").textContent = "Submit failed: " + e.message;
      $("submitBtn").disabled = false;
    } finally { state.submitting = false; }
  }

  // ---- Report -------------------------------------------------------------
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c])); }

  function renderReport(rep) {
    const comp = rep.competence || {}, deliv = rep.delivery_observations || {};
    const sp = deliv.speech || {}, bd = deliv.body || {};
    let h = "";
    h += `<div class="rep-section"><h3>Competence (content correctness)</h3>`;
    h += `<div class="stat"><span class="v">${esc(comp.overall_ability_elo)}</span><span class="k">Overall Elo</span></div>`;
    h += `<div class="stat"><span class="v">${esc(comp.questions_answered)}</span><span class="k">Answered</span></div>`;
    h += `<div class="stat"><span class="v">${esc(comp.final_phase)}</span><span class="k">Final phase</span></div>`;
    const topics = comp.topic_ability_elo || {};
    if (Object.keys(topics).length) {
      h += `<div style="margin-top:8px">` + Object.entries(topics)
        .map(([t, a]) => `<span class="chip">${esc(t)}: ${esc(Math.round(a))} Elo</span>`).join("") + `</div>`;
    }
    h += `</div>`;

    h += `<div class="rep-section"><h3>Per-question content</h3>`;
    (rep.content_breakdown || []).forEach((c, i) => {
      const sc = (typeof c.content_score === "number") ? c.content_score.toFixed(2) : "n/a";
      h += `<div class="item"><div class="top"><span>${i + 1}. ${esc(c.topic || c.category || "")}</span>`;
      h += `<span class="score">content ${sc} <span class="chip">${esc(c.content_source)}</span></span></div>`;
      if (c.question_text) h += `<div class="q">${esc(c.question_text)}</div>`;
      if (c.missing_points && c.missing_points.length)
        h += `<div class="missing">Missing: ${esc(c.missing_points.slice(0, 4).join("; "))}</div>`;
      h += `</div>`;
    });
    h += `</div>`;

    h += `<div class="rep-section"><h3>Delivery observations <span style="font-weight:400;color:var(--text-subtle);font-size:12px">(descriptive only — never scored)</span></h3>`;
    h += `<p class="muted">Speech: mean ${esc(sp.mean_words_per_minute)} wpm · filler ${esc(sp.mean_filler_rate_per_min)}/min · ${esc(sp.total_long_pauses)} long pause(s) over ${esc(sp.answers_with_speech_signal)} answer(s).</p>`;
    if (bd.answers_with_body_signal)
      h += `<p class="muted">On-camera: face-present ${esc(bd.mean_face_present_ratio)} · centered ${esc(bd.mean_centered_ratio)} · head-motion ${esc(bd.mean_head_motion)} over ${esc(bd.answers_with_body_signal)} answer(s).</p>`;
    h += `</div>`;

    h += `<div class="rep-section"><h3>Recommendations (content practice)</h3><ul class="recs">`;
    (rep.recommendations || []).forEach((r) => { h += `<li>${esc(r)}</li>`; });
    h += `</ul></div>`;
    if (rep.disclaimer) h += `<p class="hint">${esc(rep.disclaimer)}</p>`;
    $("reportBody").innerHTML = h;
  }

  async function showReport() {
    if (listening) stopMic();
    stopCamera();
    show("report");
    $("reportBody").innerHTML = '<p class="muted"><span class="spinner"></span> Building report…</p>';
    try { renderReport(await api("GET", "/interview/report?session_id=" + encodeURIComponent(state.sessionId))); }
    catch (e) { $("reportBody").innerHTML = `<p class="muted">Could not load report: ${esc(e.message)}</p>`; }
  }

  function downloadPdf() {
    if (!state.sessionId) return;
    window.open("/interview/report.pdf?session_id=" + encodeURIComponent(state.sessionId) + "&save=true", "_blank");
  }

  async function deleteSession() {
    if (!state.sessionId) return;
    if (!confirm("Permanently delete all stored data for this session? This cannot be undone.")) return;
    try {
      await api("DELETE", "/interview/session/" + encodeURIComponent(state.sessionId));
      state.sessionId = null;
      $("reportStatus").textContent = "Session data deleted.";
      toast("Session data deleted.");
    } catch (e) { $("reportStatus").textContent = "Delete failed: " + e.message; }
  }

  // ---- Wire up ------------------------------------------------------------
  $("parseBtn").addEventListener("click", parseResume);
  $("startBtn").addEventListener("click", startInterview);
  $("micBtn").addEventListener("click", () => (listening ? stopMic() : startMic()));
  $("replayBtn").addEventListener("click", () => state.question && speak(state.question.text));
  $("submitBtn").addEventListener("click", submitAnswer);
  $("nextBtn").addEventListener("click", loadNext);
  $("finishBtn").addEventListener("click", showReport);
  $("pdfBtn").addEventListener("click", downloadPdf);
  $("againBtn").addEventListener("click", () => window.location.reload());
  $("deleteBtn").addEventListener("click", deleteSession);
  if (!SR) $("micStatus").textContent = "Speech recognition needs Chrome — you can type answers instead.";
  window.addEventListener("beforeunload", stopCamera);
})();
