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
  internal_monologue?: string;
  graph_context?: string;
};

type WorldState = {
  rumor_heat: number;
  guard_alert_level: number;
  shop_price_modifier: number;
  last_event: string;
  rumor_log: { speaker: string; content: string; delta: string }[];
};

type PropagationStats = {
  active: boolean;
  message: string;
  total_experiments?: number;
  total_agents_reached?: number;
  personality_analysis?: {
    gossip: { count: number; avg_similarity: number; mutation_rate: number };
    stoic: { count: number; avg_similarity: number; mutation_rate: number };
    neutral: { count: number; avg_similarity: number; mutation_rate: number };
  };
  propagation_comparison?: {
    gossip_spreads_faster: boolean;
    gossip_to_stoic_ratio: number;
  };
  information_fidelity?: {
    avg_similarity_overall: number;
  };
};

type ExperimentTrace = {
  turn: number;
  agent_id: string;
  agent_name: string;
  personality_type: string;
  content: string;
  similarity: number;
  mutation: string;
  timestamp: string;
};

type Experiment = {
  experiment_id: string;
  secret: string;
  seed_agent: { id: string; name: string };
  start_time: string;
  total_turns: number;
  agents_reached: string[];
  propagation_rate: number;
  traces: ExperimentTrace[];
};

const API_URL = import.meta.env.VITE_BACKEND_URL ?? "http://localhost:8000";
const WS_URL = import.meta.env.VITE_BACKEND_WS ?? "ws://localhost:8000/ws/dialogue";

function App() {
  const [history, setHistory] = useState<DialogueTurn[]>([]);
  const [worldState, setWorldState] = useState<WorldState | null>(null);
  const [autoPlay, setAutoPlay] = useState(false);
  const [statusMessage, setStatusMessage] = useState("Idle");
  const [activeTab, setActiveTab] = useState<"gossip" | "experiments">("gossip");
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
          
          {/* Tab Navigation */}
          <div className="tab-nav">
            <button 
              className={`tab-btn ${activeTab === "gossip" ? "active" : ""}`}
              onClick={() => setActiveTab("gossip")}
            >
              💬 Gossip Feed
            </button>
            <button 
              className={`tab-btn ${activeTab === "experiments" ? "active" : ""}`}
              onClick={() => setActiveTab("experiments")}
            >
              📊 Propagation Lab
            </button>
          </div>
          
          {activeTab === "gossip" && (
            <div className="controls">
              <button className="primary" onClick={triggerSingleExchange}>
                Single Exchange
              </button>
              <button className="secondary" onClick={() => setAutoPlay((value) => !value)}>
                {autoPlay ? "Pause Loop" : "Autoplay Gossip"}
              </button>
            </div>
          )}
          <p className="status">Status: {statusMessage}</p>
        </section>
        {worldState && activeTab === "gossip" && (
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

      {activeTab === "gossip" ? (
        <main className="panel">
          <h2>Gossip Timeline</h2>
          <p className="hint">💭 Click any dialogue to reveal the NPC's hidden thoughts</p>
          {history.length === 0 && <p className="muted">No dialogue yet.</p>}
          <ul className="timeline">
            {history.map((turn, index) => (
              <ThoughtBubbleCard key={`${turn.timestamp}-${index}`} turn={turn} />
            ))}
          </ul>
        </main>
      ) : (
        <PropagationDashboard />
      )}
    </div>
  );
}

/** Expandable card that reveals NPC's internal monologue on click */
function ThoughtBubbleCard({ turn }: { turn: DialogueTurn }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <li 
      className={`dialogue-card ${expanded ? "expanded" : ""}`}
      onClick={() => setExpanded((v) => !v)}
    >
      <div className="turn-heading">
        <span className="speaker">{turn.speaker}</span>
        <span className="arrow">→</span>
        <span className="listener">{turn.listener}</span>
        <span className="delta">Δ {turn.rumor_delta.toFixed(2)}</span>
      </div>
      <p className="muted">
        {turn.speaker_profession} ({turn.speaker_mood}) → {turn.listener_profession} ({turn.listener_mood}) · {turn.sentiment}
      </p>
      
      {/* Internal Monologue - Chain of Thought */}
      {expanded && (
        <div className="thought-bubble">
          <span className="thought-icon">💭</span>
          <span className="thought-label">Internal:</span>
          <span className="thought-text">
            "{turn.internal_monologue || "..."}"
          </span>
        </div>
      )}
      
      {/* Spoken Dialogue */}
      <div className="spoken-dialogue">
        {expanded && <span className="spoken-label">💬 Spoken:</span>}
        <p className={expanded ? "spoken-text" : ""}>{turn.content}</p>
      </div>
      
      {/* Graph Context (if available) */}
      {expanded && turn.graph_context && (
        <div className="graph-context">
          <span className="context-icon">🔗</span>
          <span className="context-text">{turn.graph_context}</span>
        </div>
      )}
      
      <small>{new Date(turn.timestamp).toLocaleTimeString()}</small>
    </li>
  );
}

/** Propagation Experiment Dashboard */
function PropagationDashboard() {
  const [stats, setStats] = useState<PropagationStats | null>(null);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [secret, setSecret] = useState("The blacksmith is secretly a royal spy.");
  const [rounds, setRounds] = useState(15);
  const [isRunning, setIsRunning] = useState(false);
  const [runProgress, setRunProgress] = useState(0);

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_URL}/api/experiment/stats`);
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error("Failed to fetch stats:", error);
    }
  };

  const fetchTimeline = async () => {
    try {
      const response = await fetch(`${API_URL}/api/experiment/timeline`);
      const data = await response.json();
      setExperiments(data.experiments || []);
    } catch (error) {
      console.error("Failed to fetch timeline:", error);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchTimeline();
  }, []);

  const runExperiment = async () => {
    setIsRunning(true);
    setRunProgress(0);
    
    try {
      // Inject the secret
      await fetch(`${API_URL}/api/experiment/inject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ secret }),
      });
      
      // Run steps incrementally
      for (let i = 0; i < rounds; i++) {
        await fetch(`${API_URL}/api/experiment/step`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ steps: 1 }),
        });
        setRunProgress(Math.round(((i + 1) / rounds) * 100));
        
        // Refresh stats every few steps
        if (i % 3 === 0) {
          await fetchStats();
          await fetchTimeline();
        }
      }
      
      // Final refresh
      await fetchStats();
      await fetchTimeline();
    } catch (error) {
      console.error("Experiment failed:", error);
    } finally {
      setIsRunning(false);
    }
  };

  const personalityStats = stats?.personality_analysis;

  return (
    <main className="panel experiment-dashboard">
      <h2>🧪 Propagation Experiment Lab</h2>
      <p className="hint">Inject a secret and watch how it spreads through the NPC network. Compare gossip vs stoic personalities!</p>
      
      {/* Experiment Controls */}
      <div className="experiment-controls">
        <div className="input-group">
          <label>Secret to inject:</label>
          <input
            type="text"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
            placeholder="Enter a secret..."
            disabled={isRunning}
          />
        </div>
        <div className="input-group small">
          <label>Rounds:</label>
          <input
            type="number"
            value={rounds}
            onChange={(e) => setRounds(parseInt(e.target.value) || 10)}
            min={5}
            max={50}
            disabled={isRunning}
          />
        </div>
        <button 
          className="primary run-btn" 
          onClick={runExperiment}
          disabled={isRunning}
        >
          {isRunning ? `Running... ${runProgress}%` : "🚀 Run Experiment"}
        </button>
      </div>
      
      {isRunning && (
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${runProgress}%` }} />
        </div>
      )}
      
      {/* Stats Dashboard */}
      {stats?.active && personalityStats && (
        <div className="stats-grid">
          <div className="stat-card gossip">
            <div className="stat-icon">🗣️</div>
            <div className="stat-label">Gossip Types</div>
            <div className="stat-value">{personalityStats.gossip.count}</div>
            <div className="stat-sub">
              <span>Fidelity: {(personalityStats.gossip.avg_similarity * 100).toFixed(0)}%</span>
              <span>Mutations: {(personalityStats.gossip.mutation_rate * 100).toFixed(0)}%</span>
            </div>
          </div>
          
          <div className="stat-card stoic">
            <div className="stat-icon">🤫</div>
            <div className="stat-label">Stoic Types</div>
            <div className="stat-value">{personalityStats.stoic.count}</div>
            <div className="stat-sub">
              <span>Fidelity: {(personalityStats.stoic.avg_similarity * 100).toFixed(0)}%</span>
              <span>Mutations: {(personalityStats.stoic.mutation_rate * 100).toFixed(0)}%</span>
            </div>
          </div>
          
          <div className="stat-card neutral">
            <div className="stat-icon">😐</div>
            <div className="stat-label">Neutral Types</div>
            <div className="stat-value">{personalityStats.neutral.count}</div>
            <div className="stat-sub">
              <span>Fidelity: {(personalityStats.neutral.avg_similarity * 100).toFixed(0)}%</span>
              <span>Mutations: {(personalityStats.neutral.mutation_rate * 100).toFixed(0)}%</span>
            </div>
          </div>
          
          <div className="stat-card summary">
            <div className="stat-icon">📈</div>
            <div className="stat-label">Key Findings</div>
            <div className="stat-findings">
              <div className={`finding ${stats.propagation_comparison?.gossip_spreads_faster ? "positive" : "negative"}`}>
                {stats.propagation_comparison?.gossip_spreads_faster 
                  ? "✅ Gossips spread faster" 
                  : "❌ Stoics hold secrets better"}
              </div>
              <div className="finding-ratio">
                Gossip/Stoic ratio: <strong>{stats.propagation_comparison?.gossip_to_stoic_ratio.toFixed(1)}x</strong>
              </div>
              <div className="finding-fidelity">
                Overall fidelity: <strong>{((stats.information_fidelity?.avg_similarity_overall || 0) * 100).toFixed(0)}%</strong>
              </div>
            </div>
          </div>
        </div>
      )}
      
      {!stats?.active && (
        <div className="empty-state">
          <p>🔬 No experiments yet. Inject a secret to begin tracking propagation!</p>
        </div>
      )}
      
      {/* Experiment Timeline */}
      {experiments.length > 0 && (
        <div className="experiments-section">
          <h3>📜 Experiment History</h3>
          {experiments.map((exp) => (
            <ExperimentCard key={exp.experiment_id} experiment={exp} />
          ))}
        </div>
      )}
    </main>
  );
}

/** Individual experiment result card */
function ExperimentCard({ experiment }: { experiment: Experiment }) {
  const [expanded, setExpanded] = useState(false);
  
  return (
    <div className={`experiment-card ${expanded ? "expanded" : ""}`} onClick={() => setExpanded(!expanded)}>
      <div className="exp-header">
        <span className="exp-id">{experiment.experiment_id}</span>
        <span className="exp-secret">"{experiment.secret.slice(0, 40)}..."</span>
        <span className="exp-stats">
          {experiment.agents_reached.length} agents · {experiment.total_turns} turns
        </span>
      </div>
      
      {expanded && (
        <div className="exp-details">
          <div className="exp-meta">
            <span>🎯 Seed: <strong>{experiment.seed_agent.name}</strong></span>
            <span>📊 Rate: <strong>{experiment.propagation_rate.toFixed(3)}</strong> agents/turn</span>
          </div>
          
          {experiment.traces.length > 0 && (
            <div className="traces-list">
              <h4>Propagation Trail:</h4>
              {experiment.traces.slice(0, 10).map((trace, idx) => (
                <div key={idx} className={`trace-item ${trace.personality_type}`}>
                  <span className="trace-turn">T{trace.turn}</span>
                  <span className={`trace-personality ${trace.personality_type}`}>
                    {trace.personality_type === "gossip" ? "🗣️" : trace.personality_type === "stoic" ? "🤫" : "😐"}
                  </span>
                  <span className="trace-name">{trace.agent_name}</span>
                  <span className="trace-similarity">{(trace.similarity * 100).toFixed(0)}%</span>
                  <span className="trace-mutation">{trace.mutation}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
