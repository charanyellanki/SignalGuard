import { useEffect, useRef, useState } from "react";

type Status = "connecting" | "open" | "closed";

interface UseWebSocketOptions<T> {
  url: string;
  parse: (raw: string) => T | null;
  maxBuffer?: number;
  onMessage?: (item: T) => void;
}

interface UseWebSocketReturn<T> {
  status: Status;
  messages: T[];
  reconnects: number;
}

/**
 * Minimal WebSocket hook with exponential-backoff reconnect.
 *
 * - Holds the last `maxBuffer` parsed messages (newest first) for rendering.
 * - Reconnects on close with backoff capped at 10s.
 * - Cleans up on unmount — no stale sockets.
 */
export function useWebSocket<T>({
  url,
  parse,
  maxBuffer = 100,
  onMessage,
}: UseWebSocketOptions<T>): UseWebSocketReturn<T> {
  const [status, setStatus] = useState<Status>("connecting");
  const [messages, setMessages] = useState<T[]>([]);
  const [reconnects, setReconnects] = useState(0);
  const attempt = useRef(0);
  const closedByUser = useRef(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    closedByUser.current = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      setStatus("connecting");
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        attempt.current = 0;
        setStatus("open");
      };

      ws.onmessage = (ev) => {
        const parsed = parse(ev.data as string);
        if (parsed === null) return;
        onMessage?.(parsed);
        setMessages((prev) => [parsed, ...prev].slice(0, maxBuffer));
      };

      ws.onerror = () => {
        // Let onclose drive the reconnect.
      };

      ws.onclose = () => {
        setStatus("closed");
        if (closedByUser.current) return;
        attempt.current += 1;
        setReconnects((n) => n + 1);
        const delay = Math.min(10_000, 500 * 2 ** attempt.current);
        retryTimer = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      closedByUser.current = true;
      if (retryTimer) clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, [url, parse, maxBuffer, onMessage]);

  return { status, messages, reconnects };
}
