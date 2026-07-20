import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Browser voice capabilities for the AI Assistant — fully client-side:
 *   - Speech-to-Text via the Web Speech API (SpeechRecognition)
 *   - Text-to-Speech via speechSynthesis
 *
 * No backend, no API keys. Gracefully reports when a capability is unsupported
 * (e.g. Firefox lacks SpeechRecognition) so the UI can adapt.
 */
export function useSpeech() {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [speaking, setSpeaking] = useState(false);

  const recognitionRef = useRef(null);
  const onFinalRef = useRef(null);

  const SR =
    typeof window !== "undefined" &&
    (window.SpeechRecognition || window.webkitSpeechRecognition);
  const sttSupported = Boolean(SR);
  const ttsSupported =
    typeof window !== "undefined" && "speechSynthesis" in window;

  const start = useCallback(
    (onFinal) => {
      if (!SR) return;
      try {
        recognitionRef.current?.abort();
      } catch {
        /* ignore */
      }
      const rec = new SR();
      rec.lang = "en-US";
      rec.interimResults = true;
      rec.continuous = false;
      rec.maxAlternatives = 1;
      onFinalRef.current = onFinal;

      rec.onresult = (event) => {
        let interimText = "";
        let finalText = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) finalText += transcript;
          else interimText += transcript;
        }
        setInterim(interimText);
        if (finalText) {
          setInterim("");
          onFinalRef.current?.(finalText.trim());
        }
      };
      rec.onend = () => {
        setListening(false);
        setInterim("");
      };
      rec.onerror = () => {
        setListening(false);
        setInterim("");
      };

      recognitionRef.current = rec;
      setListening(true);
      try {
        rec.start();
      } catch {
        setListening(false);
      }
    },
    [SR],
  );

  const stop = useCallback(() => {
    try {
      recognitionRef.current?.stop();
    } catch {
      /* ignore */
    }
    setListening(false);
  }, []);

  const speak = useCallback(
    (text) => {
      if (!ttsSupported || !text) return;
      window.speechSynthesis.cancel();
      // Strip markdown-ish punctuation so it reads naturally.
      const clean = text
        .replace(/[*_`#>]/g, " ")
        .replace(/\n+/g, ". ")
        .replace(/\s+/g, " ")
        .trim();
      const utterance = new SpeechSynthesisUtterance(clean);
      utterance.lang = "en-US";
      utterance.rate = 1.02;
      utterance.pitch = 1.0;
      utterance.onstart = () => setSpeaking(true);
      utterance.onend = () => setSpeaking(false);
      utterance.onerror = () => setSpeaking(false);
      window.speechSynthesis.speak(utterance);
    },
    [ttsSupported],
  );

  const cancelSpeak = useCallback(() => {
    if (ttsSupported) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, [ttsSupported]);

  // Clean up on unmount.
  useEffect(() => {
    return () => {
      try {
        recognitionRef.current?.abort();
      } catch {
        /* ignore */
      }
      if (ttsSupported) window.speechSynthesis.cancel();
    };
  }, [ttsSupported]);

  return {
    listening,
    interim,
    start,
    stop,
    sttSupported,
    speak,
    cancelSpeak,
    speaking,
    ttsSupported,
  };
}
