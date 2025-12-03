import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

type DialogueTurn = {
  speaker: string;
  listener: string;
  speaker_profession: string;
  listener_profession: string;
  speaker_mood: string;
  listener_mood: string;
  content: string;
  rumor_delta: number;
  sentiment: string;
  timestamp: string;
};

type WorldState = {
  rumor_heat: number;
  guard_alert_level: number;
  shop_price_modifier: number;
  last_event: string;
  rumor_log: { speaker: string; content: string; delta: string }[];
};

const API_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";
const WS_URL = import.meta.env.VITE_BACKEND_WS ?? "ws://localhost:8000/ws/dialogue";

function App() {
  const [history, setHistory] = useState<DialogueTurn[]>([]);
  const [worldState, setWorldState] = useState<WorldState | null>(null);
  const [autoPlay, setAutoPlay] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Idle");
  const socketRef = useRef<WebSocket | null>(null);

  const fetchSnapshot = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/state`);
      if (!response.ok) throw new Error("State request failed");
      const payload = await response.json();
      setWorldState(payload.world_state);
      setHistory(
        (payload.history ?? []).map((turn: Omit<DialogueTurn, "timestamp">) => ({
          ...turn,
          timestamp: new Date().toISOString(),
        })),
      );
    } catch (error) {
      setStatusMessage((error as Error).message);
    }
  }, []);

  useEffect(() => {
    fetchSnapshot();
  }, [fetchSnapshot]);

  const connectSocket = useCallback(() => {
    const socket = new WebSocket(WS_URL);
    socket.onopen = () => setStatusMessage("Agents gossiping...");
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      const turn = payload.turn as Omit<DialogueTurn, "timestamp">;
      setHistory((prev) => {
        const next = [
          ...prev,
          {
            ...turn,
            timestamp: new Date().toISOString(),
          },
        ];
        return next.slice(-25);
      });
      setWorldState(payload.world_state as WorldState);
    };
    socket.onerror = () => setStatusMessage("WebSocket error");
    socket.onclose = () => setStatusMessage("Connection ended");
    socketRef.current = socket;
    return socket;
  }, []);

  useEffect(() => {
    if (!autoPlay) {
      socketRef.current?.close();
      socketRef.current = null;
      return;
    }
    const socket = connectSocket();
    return () => socket.close();
  }, [autoPlay, connectSocket]);

  const triggerSingleExchange = async () => {
    setStatusMessage("Triggering rumor...");
    try {
      const response = await fetch(`${API_URL}/api/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ steps: 1 }),
      });
      if (!response.ok) throw new Error("Failed to run step");
      const data = await response.json();
      setWorldState(data.world_state as WorldState);
      setHistory((prev) => {
        const next = [
          ...prev,
          ...data.history.map((turn: Omit<DialogueTurn, "timestamp">) => ({
            ...turn,
            timestamp: new Date().toISOString(),
          })),
        ];
        return next.slice(-25);
      });
      setStatusMessage("Idle");
    } catch (error) {
      setStatusMessage((error as Error).message);
    }
  };

  const rumorMeter = useMemo(() => {
    if (!worldState) return 0;
    return Math.min(100, Math.round(worldState.rumor_heat * 100));
  }, [worldState]);

  return (
    <div className="layout">
      <header className="panel">
        <section>
          <h1>Dynamic NPC Ecosystem</h1>
          <p>Watch the townsfolk gossip without the player lifting a finger—each reset assembles a fresh duo.</p>
          <div className="controls">
            <button className="primary" onClick={triggerSingleExchange}>
              Single Exchange
            </button>
            <button className="secondary" onClick={() => setAutoPlay((value) => !value)}>
              {autoPlay ? "Pause Loop" : "Autoplay Gossip"}
            </button>
          </div>
          <p className="status">Status: {statusMessage}</p>
        </section>
        {worldState && (
          <section className="world-state">
            <h2>Rumor Telemetry</h2>
            <div className="meter">
              <div className="meter-fill" style={{ width: `${rumorMeter}%` }} />
            </div>
            <ul>
              <li>Guard alert: {Math.round(worldState.guard_alert_level * 100)}%</li>
              <li>Shop markup: {(worldState.shop_price_modifier * 100).toFixed(0)}%</li>
              <li>Anchor memory: {worldState.last_event}</li>
            </ul>
          </section>
        )}
      </header>

      <main className="panel">
        <h2>Gossip Timeline</h2>
        {history.length === 0 && <p className="muted">No dialogue yet.</p>}
        <ul className="timeline">
          {history.map((turn, index) => (
            <li key={`${turn.timestamp}-${index}`}>
              <div className="turn-heading">
                <span className="speaker">{turn.speaker}</span>
                <span className="arrow">→</span>
                <span className="listener">{turn.listener}</span>
                <span className="delta">Δ {turn.rumor_delta.toFixed(2)}</span>
              </div>
              <p className="muted">
                {turn.speaker_profession} ({turn.speaker_mood}) → {turn.listener_profession} ({turn.listener_mood}) · {turn.sentiment}
              </p>
              <p>{turn.content}</p>
              <small>{new Date(turn.timestamp).toLocaleTimeString()}</small>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}

export default App;
