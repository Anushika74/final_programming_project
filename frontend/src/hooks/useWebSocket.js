import { useEffect, useRef, useState, useCallback } from "react";
import { getToken } from "../api/client";

// Resolve the WebSocket URL: explicit env var, otherwise derive from the page.
function resolveWsUrl() {
  const explicit = import.meta.env.VITE_WS_URL;
  if (explicit) return explicit;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/metrics`;
}

/**
 * Subscribe to the live WebSocket. Auto-reconnects with backoff.
 * Handles both software metrics ("metrics") and hardware sensors ("hardware").
 * Returns { metrics, hardware, connected, history, hardwareHistory } where the
 * history fields are rolling buffers suitable for live charts.
 */
export function useMetricsSocket(bufferSize = 60) {
  const [metrics, setMetrics] = useState(null);
  const [hardware, setHardware] = useState(null);
  const [connected, setConnected] = useState(false);
  const [history, setHistory] = useState([]);
  const [hardwareHistory, setHardwareHistory] = useState([]);
  const socketRef = useRef(null);
  const reconnectRef = useRef(null);
  const attemptsRef = useRef(0);

  const connect = useCallback(() => {
    const token = getToken();
    const url = token ? `${resolveWsUrl()}?token=${token}` : resolveWsUrl();
    const ws = new WebSocket(url);
    socketRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      attemptsRef.current = 0;
      // Keepalive ping so the server's receive loop stays active.
      ws.pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, 15000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "metrics") {
          setMetrics(data.payload);
          setHistory((prev) => {
            const next = [...prev, { ...data.payload, t: Date.now() }];
            return next.slice(-bufferSize);
          });
        } else if (data.type === "hardware") {
          setHardware(data.payload);
          setHardwareHistory((prev) => {
            const next = [...prev, { ...data.payload, t: Date.now() }];
            return next.slice(-bufferSize);
          });
        }
      } catch {
        /* ignore malformed frames */
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (ws.pingInterval) clearInterval(ws.pingInterval);
      // Exponential backoff up to ~10s.
      attemptsRef.current += 1;
      const delay = Math.min(10000, 500 * 2 ** attemptsRef.current);
      reconnectRef.current = setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, [bufferSize]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (socketRef.current) {
        socketRef.current.onclose = null;
        socketRef.current.close();
      }
    };
  }, [connect]);

  return { metrics, hardware, connected, history, hardwareHistory };
}
