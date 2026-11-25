import { useEffect, useRef, useState } from "react";

const API = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

// A new session starts on each page load.
const newSessionId = () => "s-" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);

function errorText(status, body) {
  const d = body && body.detail;
  if (status === 503) return "All AI providers are unavailable right now. Please try again in a moment.";
  if (status === 422) {
    if (Array.isArray(d) && d.length) return "Your message was rejected: " + d.map((e) => e.msg).join("; ");
    return "Your message was rejected. Messages must be 1–4000 characters.";
  }
  if (typeof d === "string") return d;
  return "Something went wrong. Please try again.";
}

function AssistantMessage({ m }) {
  const meta = m.metadata;
  return (
    <div className="row row-bot">
      <div className="bubble bot" data-testid="assistant-message">
        <p className="text">{m.content}</p>
        {meta && (
          <dl className="meta">
            <div><dt>Source</dt>
              <dd data-testid="meta-source" className={meta.resolution_source === "LLM_CACHE" ? "chip cache" : "chip live"}>
                {meta.resolution_source}
              </dd></div>
            <div><dt>Model</dt><dd data-testid="meta-model">{meta.model}</dd></div>
            <div><dt>Latency</dt><dd data-testid="meta-latency">{meta.latency_ms} ms</dd></div>
            <div><dt>Input tokens</dt><dd data-testid="meta-input-tokens">{meta.input_tokens}</dd></div>
            <div><dt>Output tokens</dt><dd data-testid="meta-output-tokens">{meta.output_tokens}</dd></div>
            {meta.key_id && <div><dt>Key</dt><dd>{meta.key_id}{meta.fallback_attempts ? ` (after ${meta.fallback_attempts} failed)` : ""}</dd></div>}
          </dl>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [sessionId] = useState(newSessionId);
  const [items, setItems] = useState([]);
  const [input, setInput] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [simulate, setSimulate] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [items, busy]);

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setItems((p) => [...p, { kind: "user", content: text }]);
    try {
      const headers = { "Content-Type": "application/json" };
      if (simulate.trim()) headers["X-Simulate-Failure"] = simulate.trim();
      const body = { session_id: sessionId, message: text };
      if (systemPrompt.trim()) body.system_prompt = systemPrompt.trim();
      const res = await fetch(`${API}/chat`, { method: "POST", headers, body: JSON.stringify(body) });
      let data = null;
      try { data = await res.json(); } catch { /* non-JSON body */ }
      if (!res.ok) {
        setItems((p) => [...p, { kind: "error", content: errorText(res.status, data) }]);
      } else {
        setItems((p) => [...p, { kind: "assistant", content: data.reply, metadata: data.metadata }]);
      }
    } catch {
      setItems((p) => [...p, { kind: "error", content: "Can't reach the server. Check your connection and try again." }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <header className="top">
        <h1>Relay Chat</h1>
        <span className="sid">session {sessionId}</span>
      </header>

      <details className="settings">
        <summary>Session settings</summary>
        <label>System prompt
          <textarea data-testid="system-prompt-input" rows={2} value={systemPrompt}
            onChange={(e) => setSystemPrompt(e.target.value)}
            placeholder="Optional. Applies to this session, e.g. “Answer like a pirate.”" />
        </label>
        <label>Simulate failure (demo)
          <input value={simulate} onChange={(e) => setSimulate(e.target.value)}
            placeholder="key_1=429  or  *=429" />
        </label>
      </details>

      <main className="log" aria-live="polite">
        {items.length === 0 && <p className="empty">Ask anything. Each reply shows where it came from, how long it took, and its token use.</p>}
        {items.map((m, i) =>
          m.kind === "user" ? (
            <div className="row row-user" key={i}><div className="bubble user">{m.content}</div></div>
          ) : m.kind === "error" ? (
            <div className="row row-bot" key={i}><div className="bubble err" role="alert">{m.content}</div></div>
          ) : (
            <AssistantMessage m={m} key={i} />
          )
        )}
        {busy && <div className="row row-bot"><div className="bubble bot thinking">Thinking…</div></div>}
        <div ref={endRef} />
      </main>

      <footer className="composer">
        <textarea data-testid="chat-input" rows={1} value={input} placeholder="Type a message"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
        <button data-testid="send-button" onClick={send} disabled={busy || !input.trim()}>Send</button>
      </footer>
    </div>
  );
}
