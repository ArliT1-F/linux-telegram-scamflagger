"""Vercel-hostable Flask app for scam/promo message analysis."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, send_file

from detector import DEFAULT_CONFIG, analyze_message, confidence_label
from registry import (
    RegistryConfig,
    append_registry_entry,
    classify_scam_type,
    get_download_status,
    publish_registry_updates_if_due,
)

app = Flask(__name__)

MAX_MESSAGE_LENGTH = 5000
registry_config = RegistryConfig(
    live_file=Path("scam_registry_live.txt"),
    download_dir=Path("registry_downloads"),
    download_meta_file=Path("registry_download_meta.json"),
    cooldown_days=30,
)

HOME_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Telegram Scam & Promo Analyzer</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #0b1020;
      --card: #131a2a;
      --text: #eef2ff;
      --muted: #9aa4bf;
      --accent: #4f8cff;
      --danger: #ef4444;
      --ok: #10b981;
      --warn: #f59e0b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      background: radial-gradient(circle at 20% 0%, #1f2a44 0, var(--bg) 60%);
      color: var(--text);
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    .wrap {
      width: min(820px, 100%);
      background: color-mix(in oklab, var(--card), transparent 10%);
      border: 1px solid color-mix(in oklab, var(--muted), transparent 70%);
      border-radius: 16px;
      padding: 20px;
      box-shadow: 0 12px 32px rgba(0,0,0,0.3);
    }
    h1 { margin-top: 0; font-size: 1.4rem; }
    p { color: var(--muted); line-height: 1.45; }
    textarea {
      width: 100%;
      min-height: 180px;
      border: 1px solid color-mix(in oklab, var(--muted), transparent 60%);
      background: #0a1020;
      color: var(--text);
      border-radius: 12px;
      padding: 12px;
      resize: vertical;
      font-size: 0.96rem;
    }
    .row {
      display: flex;
      gap: 12px;
      align-items: center;
      margin-top: 12px;
      flex-wrap: wrap;
    }
    button {
      background: var(--accent);
      color: white;
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      font-weight: 600;
      cursor: pointer;
    }
    button:disabled { opacity: 0.65; cursor: not-allowed; }
    .hint { color: var(--muted); font-size: 0.88rem; }
    .result {
      margin-top: 16px;
      border-radius: 12px;
      border: 1px solid color-mix(in oklab, var(--muted), transparent 60%);
      padding: 12px;
      display: none;
      background: #0d1326;
    }
    .badge {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
      letter-spacing: 0.02em;
    }
    .HIGH { background: color-mix(in oklab, var(--danger), transparent 60%); color: #fecaca; }
    .MEDIUM { background: color-mix(in oklab, var(--warn), transparent 60%); color: #fde68a; }
    .LOW { background: color-mix(in oklab, var(--ok), transparent 60%); color: #a7f3d0; }
    ul { margin-bottom: 0; }
    code {
      background: #0b142f;
      border: 1px solid color-mix(in oklab, var(--muted), transparent 70%);
      border-radius: 8px;
      padding: 2px 6px;
      color: #dbeafe;
    }
  </style>
</head>
<body>
  <main class="wrap">
    <h1>Telegram Scam & Promo Analyzer</h1>
    <p>
      Paste a message to score it with transparent, rule-based detection.
      Messages at or above <code>{{ threshold }}</code> are typically considered evidence-worthy.
    </p>

    <label for="message">Message text</label>
    <textarea id="message" maxlength="5000" placeholder="Paste suspicious message here..."></textarea>

    <div class="row">
      <button id="analyze-btn" type="button">Analyze message</button>
      <span class="hint">No database, no account, no background collection.</span>
    </div>

    <section id="result" class="result">
      <div id="summary"></div>
      <h3>Reasons</h3>
      <ul id="reasons"></ul>
    </section>
  </main>

  <script>
    const btn = document.getElementById("analyze-btn");
    const msg = document.getElementById("message");
    const result = document.getElementById("result");
    const summary = document.getElementById("summary");
    const reasons = document.getElementById("reasons");

    btn.addEventListener("click", async () => {
      const message = msg.value.trim();
      if (!message) {
        alert("Please enter a message.");
        return;
      }
      btn.disabled = true;
      try {
        const resp = await fetch("/api/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message }),
        });
        const data = await resp.json();
        if (!resp.ok) {
          throw new Error(data.error || "Failed to analyze message");
        }

        summary.innerHTML = `
          <p>
            Score: <strong>${data.score}</strong> /
            Confidence: <span class="badge ${data.confidence}">${data.confidence}</span><br />
            Should Save Evidence: <strong>${data.should_save ? "Yes" : "No"}</strong>
          </p>
        `;

        reasons.innerHTML = "";
        if (!data.reasons.length) {
          const li = document.createElement("li");
          li.textContent = "No explicit rule matches found.";
          reasons.appendChild(li);
        } else {
          for (const reason of data.reasons) {
            const li = document.createElement("li");
            li.textContent = reason;
            reasons.appendChild(li);
          }
        }
        result.style.display = "block";
      } catch (err) {
        alert(err.message);
      } finally {
        btn.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


@app.after_request
def add_common_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/", methods=["GET"])
def home():
    return render_template_string(HOME_HTML, threshold=DEFAULT_CONFIG.save_threshold)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/registry/entry", methods=["POST"])
def add_registry_entry():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name", "")
    identifier = payload.get("identifier", "")
    scam_type = payload.get("scam_type", "")

    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "`name` must be a non-empty string"}), 400
    if not isinstance(identifier, str) or not identifier.strip():
        return jsonify({"error": "`identifier` must be a non-empty string"}), 400
    if not isinstance(scam_type, str) or not scam_type.strip():
        return jsonify({"error": "`scam_type` must be a non-empty string"}), 400

    score = payload.get("score", 0)
    confidence = payload.get("confidence", "MEDIUM")
    try:
        score = int(score)
    except (TypeError, ValueError):
        return jsonify({"error": "`score` must be an integer"}), 400
    if not isinstance(confidence, str):
        return jsonify({"error": "`confidence` must be a string"}), 400

    append_registry_entry(
        registry_config,
        name=name,
        identifier=identifier,
        scam_type=scam_type,
        score=max(0, min(score, 100)),
        confidence=confidence.strip().upper() or "MEDIUM",
    )
    return jsonify({"status": "ok"})


@app.route("/api/registry/download/status", methods=["GET"])
def registry_download_status():
    return jsonify(get_download_status(registry_config))


@app.route("/api/registry/publish", methods=["POST"])
def publish_registry_updates():
    status = publish_registry_updates_if_due(registry_config)
    if status["publish_allowed_now"] and status["appended_entries"] == 0:
        return jsonify(
            {
                "status": "ok",
                "message": "No pending entries to publish; download remains available.",
                "download_status": status,
            }
        )
    if not status["published_this_call"]:
        return jsonify(
            {
                "status": "cooldown_active",
                "message": "Download file is still available. Staged entries publish once per month.",
                "download_status": status,
            }
        ), 429

    return jsonify(
        {
            "status": "ok",
            "download_status": status,
            "appended_entries": status["appended_entries"],
        }
    )


@app.route("/api/registry/download", methods=["GET"])
def download_registry_snapshot():
    status = get_download_status(registry_config)
    snapshot_file = status.get("snapshot_file")
    if not snapshot_file:
        return jsonify({"error": "No downloadable registry snapshot is set up yet."}), 404

    path = Path(snapshot_file)
    if not path.exists():
        return jsonify({"error": "Snapshot file is missing on server."}), 404

    return send_file(path, as_attachment=True, download_name=path.name, mimetype="text/plain")


@app.route("/api/analyze", methods=["POST", "OPTIONS"])
def analyze():
    if request.method == "OPTIONS":
        return ("", 204)

    payload = request.get_json(silent=True) or {}
    message = payload.get("message", "")
    if not isinstance(message, str):
        return jsonify({"error": "`message` must be a string"}), 400

    message = message.strip()
    if not message:
        return jsonify({"error": "`message` cannot be empty"}), 400
    if len(message) > MAX_MESSAGE_LENGTH:
        return jsonify({"error": f"`message` exceeds max length {MAX_MESSAGE_LENGTH}"}), 400

    score, reasons = analyze_message(message)
    confidence = confidence_label(score)
    inferred_scam_type = classify_scam_type(reasons)
    maybe_name = payload.get("name")
    maybe_identifier = payload.get("identifier")
    if isinstance(maybe_name, str) and maybe_name.strip() and isinstance(maybe_identifier, str) and maybe_identifier.strip():
        append_registry_entry(
            registry_config,
            name=maybe_name,
            identifier=maybe_identifier,
            scam_type=inferred_scam_type,
            score=score,
            confidence=confidence,
        )

    return jsonify(
        {
            "score": score,
            "confidence": confidence,
            "reasons": reasons,
            "scam_type": inferred_scam_type,
            "threshold": DEFAULT_CONFIG.save_threshold,
            "should_save": score >= DEFAULT_CONFIG.save_threshold,
        }
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
