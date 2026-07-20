import { useState, useRef, useEffect, useCallback } from "react";
import { AssistantAPI, OptimizationAPI } from "../api/endpoints";
import { useSpeech } from "../hooks/useSpeech";

const WELCOME =
  "Hi! I'm the SystemIQ assistant. I analyze your live metrics, hardware sensors, " +
  "processes, predictions and logs together. Ask me by text or voice — try " +
  '"why is my laptop slow?", "which app is overheating my laptop?", or "how is my system?"';

const SUGGESTIONS = [
  "How is my system?",
  "Why is my laptop slow?",
  "Why is the CPU temperature increasing?",
  "Which application is overheating my laptop?",
  "Will my system overheat soon?",
  "Why is the fan spinning so fast?",
  "Is my SSD healthy?",
  "Is my battery degrading?",
  "What should I optimize first?",
  "Explain thermal throttling",
];

function BotAvatar() {
  return (
    <div className="h-8 w-8 shrink-0 rounded-full bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-sm">
      🤖
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-4 py-3">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="typing-dot h-2 w-2 rounded-full bg-slate-400"
          style={{ animationDelay: `${i * 0.18}s` }}
        />
      ))}
    </div>
  );
}

export default function Assistant() {
  const [messages, setMessages] = useState([
    { role: "assistant", text: WELCOME },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const endRef = useRef(null);

  const {
    listening,
    interim,
    start,
    stop,
    sttSupported,
    speak,
    cancelSpeak,
    speaking,
    ttsSupported,
  } = useSpeech();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy, interim]);

  const send = useCallback(
    async (text) => {
      const query = (text ?? input).trim();
      if (!query) return;
      cancelSpeak();
      setInput("");
      setMessages((m) => [...m, { role: "user", text: query }]);
      setBusy(true);
      try {
        const res = await AssistantAPI.ask(query);
        const msg = {
          role: "assistant",
          text: res.answer,
          intent: res.intent,
          actions: res.suggested_actions || [],
          sources: res.sources || [],
        };
        setMessages((m) => [...m, msg]);
        if (autoSpeak) speak(res.answer);
      } catch {
        setMessages((m) => [
          ...m,
          {
            role: "assistant",
            text: "Sorry, I couldn't process that request.",
          },
        ]);
      } finally {
        setBusy(false);
      }
    },
    [input, autoSpeak, speak, cancelSpeak],
  );

  const handleMic = () => {
    if (listening) {
      stop();
      return;
    }
    cancelSpeak();
    start((finalText) => {
      if (finalText) send(finalText);
    });
  };

  const runAction = async (key) => {
    const res = await OptimizationAPI.execute(key, false, true);
    setMessages((m) => [
      ...m,
      { role: "assistant", text: `(${key}) ${res.message}` },
    ]);
  };

  const displayValue = listening ? interim || "Listening…" : input;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-white">AI Assistant</h1>

      <div className="card flex flex-col h-[68vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-ink-700 bg-ink-900/40">
          <div className="flex items-center gap-3">
            <BotAvatar />
            <div>
              <div className="text-sm font-semibold text-slate-100">
                SystemIQ Assistant
              </div>
              <div className="text-xs text-emerald-400 flex items-center gap-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                online · offline-capable
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {speaking && (
              <button
                onClick={cancelSpeak}
                className="text-xs bg-ink-700 hover:bg-ink-600 rounded-lg px-2 py-1 text-slate-200"
              >
                ⏹ Stop
              </button>
            )}
            {ttsSupported && (
              <button
                onClick={() => setAutoSpeak((v) => !v)}
                title="Read answers aloud"
                className={`text-xs rounded-lg px-2 py-1 transition-colors ${
                  autoSpeak
                    ? "bg-brand-600 text-white"
                    : "bg-ink-700 hover:bg-ink-600 text-slate-300"
                }`}
              >
                {autoSpeak ? "🔊 Voice on" : "🔈 Voice off"}
              </button>
            )}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex items-start gap-2 animate-fade-in ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {msg.role === "assistant" && <BotAvatar />}
              <div
                className={`max-w-[78%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-line shadow ${
                  msg.role === "user"
                    ? "bg-gradient-to-br from-brand-500 to-brand-600 text-white rounded-br-sm"
                    : "bg-ink-700 text-slate-200 rounded-bl-sm"
                }`}
              >
                <div>{msg.text}</div>

                {msg.role === "assistant" && ttsSupported && (
                  <button
                    onClick={() => speak(msg.text)}
                    className="mt-1 text-[11px] text-slate-400 hover:text-brand-400"
                    title="Read aloud"
                  >
                    🔊 Read aloud
                  </button>
                )}

                {msg.sources?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1 items-center">
                    <span className="text-[10px] uppercase tracking-wide text-slate-500 mr-1">
                      context:
                    </span>
                    {msg.sources.map((s) => (
                      <span
                        key={s}
                        className="text-[10px] bg-ink-900 text-slate-400 rounded px-1.5 py-0.5"
                      >
                        {s}
                      </span>
                    ))}
                  </div>
                )}

                {msg.actions?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {msg.actions.map((a) => (
                      <button
                        key={a.key}
                        onClick={() => runAction(a.key)}
                        className="text-xs bg-ink-900 hover:bg-ink-600 rounded-lg px-2 py-1"
                      >
                        {a.title}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {busy && (
            <div className="flex items-start gap-2">
              <BotAvatar />
              <div className="bg-ink-700 rounded-2xl rounded-bl-sm">
                <TypingIndicator />
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* Suggestions + input */}
        <div className="border-t border-ink-700 p-3 bg-ink-900/40">
          <div className="flex flex-wrap gap-2 mb-2 max-h-16 overflow-y-auto">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                disabled={busy}
                className="text-xs bg-ink-700 hover:bg-ink-600 rounded-full px-3 py-1 text-slate-300 disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
            className="flex items-center gap-2"
          >
            <input
              className={`input flex-1 ${listening ? "border-red-500 text-red-300" : ""}`}
              placeholder={
                listening ? "" : "Ask by text, or tap the mic to speak…"
              }
              value={displayValue}
              onChange={(e) => setInput(e.target.value)}
              disabled={listening}
            />

            {/* Mic button */}
            {sttSupported && (
              <button
                type="button"
                onClick={handleMic}
                title={listening ? "Stop listening" : "Speak"}
                className={`relative h-10 w-10 shrink-0 rounded-full flex items-center justify-center transition-colors ${
                  listening
                    ? "bg-red-600 text-white"
                    : "bg-ink-700 hover:bg-ink-600 text-slate-200"
                }`}
              >
                {listening && (
                  <span className="absolute inset-0 rounded-full bg-red-500/40 animate-ping" />
                )}
                <span className="relative">🎙️</span>
              </button>
            )}

            <button
              type="submit"
              className="btn-primary"
              disabled={busy || listening}
            >
              Send
            </button>
          </form>

          {!sttSupported && (
            <p className="text-[11px] text-slate-500 mt-1">
              Voice input isn't supported in this browser (try Chrome/Edge).
              Text chat works everywhere.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
