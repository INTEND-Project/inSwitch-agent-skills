import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  useEdgesState,
  useNodesState
} from 'reactflow';
import 'reactflow/dist/style.css';
import logo from './assets/intend-black.svg';

const API_URL = 'http://localhost:8085/intent';
const LOG_STREAM_URL = 'http://localhost:8085/logs/stream';

type Message = {
  id: string;
  role: 'user' | 'agent' | 'system';
  text: string;
};

type GraphKind = 'agent' | 'skill' | 'tool';

type GraphNodeData = {
  label: string;
  kind: GraphKind;
  highlighted?: boolean;
};

const buildNodeClass = (kind: GraphKind, highlighted?: boolean) =>
  `graph-node ${kind}${highlighted ? ' highlighted' : ''}`;

const initialMessages: Message[] = [
  {
    id: 'welcome',
    role: 'system',
    text: 'Hello! Ask me anything about the system and I will respond.'
  }
];

const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [logStatus, setLogStatus] = useState<'connected' | 'disconnected'>('disconnected');
  const [selectedValue, setSelectedValue] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState<GraphNodeData>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const listRef = useRef<HTMLDivElement | null>(null);
  const logListRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const nodesRef = useRef<Node<GraphNodeData>[]>([]);
  const edgesRef = useRef<Edge[]>([]);
  const nodeTimers = useRef<Map<string, number>>(new Map());
  const edgeTimers = useRef<Map<string, number>>(new Map());
  const nodeIndex = useRef(0);

  const canSend = useMemo(() => input.trim().length > 0 && !isSending, [input, isSending]);

  const scrollToBottom = useCallback(() => {
    const node = listRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    const node = logListRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [logs]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    nodesRef.current = nodes;
  }, [nodes]);

  useEffect(() => {
    edgesRef.current = edges;
  }, [edges]);

  const nextPosition = useCallback(() => {
    const index = nodeIndex.current;
    nodeIndex.current += 1;
    const cols = 3;
    const gapX = 170;
    const gapY = 140;
    return {
      x: (index % cols) * gapX,
      y: Math.floor(index / cols) * gapY
    };
  }, []);

  const highlightNode = useCallback(
    (id: string) => {
      setNodes((prev) =>
        prev.map((node) =>
          node.id === id
            ? {
                ...node,
                data: { ...node.data, highlighted: true },
                className: buildNodeClass(node.data.kind, true)
              }
            : node
        )
      );
      const existing = nodeTimers.current.get(id);
      if (existing) {
        window.clearTimeout(existing);
      }
      const timer = window.setTimeout(() => {
        setNodes((prev) =>
          prev.map((node) =>
            node.id === id
              ? {
                  ...node,
                  data: { ...node.data, highlighted: false },
                  className: buildNodeClass(node.data.kind, false)
                }
              : node
          )
        );
        nodeTimers.current.delete(id);
      }, 2000);
      nodeTimers.current.set(id, timer);
    },
    [setNodes]
  );

  const highlightEdge = useCallback(
    (id: string) => {
      setEdges((prev) =>
        prev.map((edge) =>
          edge.id === id
            ? {
                ...edge,
                data: { ...edge.data, highlighted: true },
                className: 'graph-edge highlighted'
              }
            : edge
        )
      );
      const existing = edgeTimers.current.get(id);
      if (existing) {
        window.clearTimeout(existing);
      }
      const timer = window.setTimeout(() => {
        setEdges((prev) =>
          prev.map((edge) =>
            edge.id === id
              ? {
                  ...edge,
                  data: { ...edge.data, highlighted: false },
                  className: 'graph-edge'
                }
              : edge
          )
        );
        edgeTimers.current.delete(id);
      }, 2000);
      edgeTimers.current.set(id, timer);
    },
    [setEdges]
  );

  const ensureNode = useCallback(
    (name: string, kind: GraphKind) => {
      if (!name) return;
      const existing = nodesRef.current.find((node) => node.id === name);
      if (existing) {
        highlightNode(name);
        return;
      }
      const position = nextPosition();
      const newNode: Node<GraphNodeData> = {
        id: name,
        position,
        data: { label: name, kind },
        type: 'default',
        className: buildNodeClass(kind, false)
      };
      setNodes((prev) => [...prev, newNode]);
    },
    [highlightNode, nextPosition, setNodes]
  );

  const ensureEdge = useCallback(
    (source: string, target: string, label?: string) => {
      if (!source || !target || source === target) return;
      const edgeId = `${source}__${target}`;
      const existing = edgesRef.current.find((edge) => edge.id === edgeId);
      if (existing) {
        highlightEdge(edgeId);
        return;
      }
      const newEdge: Edge = {
        id: edgeId,
        source,
        target,
        label,
        animated: false,
        className: 'graph-edge'
      };
      setEdges((prev) => [...prev, newEdge]);
    },
    [highlightEdge, setEdges]
  );

  const handleStructuredLog = useCallback(
    (entry: string) => {
      let payload: any;
      try {
        payload = JSON.parse(entry);
      } catch (err) {
        return;
      }
      const event = payload?.event;
      if (!event) return;

      if (event === 'agent_created') {
        ensureNode(payload.agent, 'agent');
        if (payload.created_by) {
          ensureNode(payload.created_by, 'agent');
          ensureEdge(payload.created_by, payload.agent, 'creates');
        }
        return;
      }

      if (event === 'skill_loaded') {
        ensureNode(payload.agent, 'agent');
        ensureNode(payload.skill, 'skill');
        ensureEdge(payload.agent, payload.skill, 'skill');
        return;
      }

      if (event === 'tool_invocation') {
        ensureNode(payload.agent, 'agent');
        ensureNode(payload.tool, 'tool');
        ensureEdge(payload.agent, payload.tool, 'calls');
        return;
      }

      if (event === 'tool_result') {
        ensureNode(payload.agent, 'agent');
        ensureNode(payload.tool, 'tool');
        ensureEdge(payload.tool, payload.agent, 'returns');
        return;
      }

      if (event === 'agent_message') {
        ensureNode(payload.from, 'agent');
        ensureNode(payload.to, 'agent');
        ensureEdge(payload.from, payload.to, 'sends');
      }
    },
    [ensureEdge, ensureNode]
  );

  useEffect(() => {
    const source = new EventSource(LOG_STREAM_URL);

    source.onopen = () => {
      setLogStatus('connected');
    };

    source.onerror = () => {
      setLogStatus('disconnected');
    };

    source.onmessage = (event) => {
      if (!event.data) return;
      setLogs((prev) => [...prev, event.data]);
      handleStructuredLog(event.data);
    };

    return () => {
      source.close();
    };
  }, []);

  const pushMessage = (message: Message) => {
    setMessages((prev) => [...prev, message]);
  };

  const sendMessage = async () => {
    if (!canSend) return;

    const trimmed = input.trim();
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      text: trimmed
    };

    setInput('');
    setError(null);
    pushMessage(userMessage);
    setIsSending(true);

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ input: trimmed })
      });

      if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
      }

      const json = (await response.json()) as { response?: string };
      const agentText = json.response ?? 'No response received.';

      pushMessage({
        id: `agent-${Date.now()}`,
        role: 'agent',
        text: agentText
      });
    } catch (err) {
      console.error(err);
      setError('Unable to reach the agent. Check that the backend is running on :8085.');
      pushMessage({
        id: `error-${Date.now()}`,
        role: 'system',
        text: 'Something went wrong while sending your message.'
      });
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  const renderLogEntry = (entry: string, index: number) => {
    let payload: any;
    try {
      payload = JSON.parse(entry);
    } catch (err) {
      return (
        <div key={`${entry}-${index}`} className="log-card">
          <div className="log-card-header">
            <span className="log-event">raw</span>
          </div>
          <div className="log-params">
            <span className="log-param">message:{entry}</span>
          </div>
        </div>
      );
    }

    const eventType = payload?.event ?? 'event';
    const timestamp = payload?.ts ?? '';
    const params: Record<string, any> = { ...payload };
    delete params.event;
    delete params.ts;

    const formatValue = (value: any) => {
      if (value === null || value === undefined) {
        return { display: String(value), full: String(value), truncated: false };
      }
      if (typeof value === 'string') {
        if (value.length > 15) {
          return { display: value.slice(0, 15), full: value, truncated: true };
        }
        return { display: value, full: value, truncated: false };
      }
      if (typeof value === 'object') {
        const json = JSON.stringify(value);
        if (json.length > 15) {
          return { display: json.slice(0, 15), full: json, truncated: true };
        }
        return { display: json, full: json, truncated: false };
      }
      const text = String(value);
      return { display: text, full: text, truncated: false };
    };

    return (
      <div key={`${entry}-${index}`} className="log-card">
        <div className="log-card-header">
          <span className="log-event">{eventType}</span>
          {timestamp && <span className="log-ts">{timestamp}</span>}
        </div>
        <div className="log-params">
          {Object.entries(params).map(([key, value]) => {
            const formatted = formatValue(value);
            const content = (
              <span className="log-value">
                {formatted.display}
                {formatted.truncated && <span className="log-ellipsis">…</span>}
              </span>
            );
            return (
              <span key={key} className="log-param">
                <span className="log-key">{key}:</span>
                {formatted.truncated ? (
                  <button
                    type="button"
                    className="log-value-button"
                    onClick={() => setSelectedValue(formatted.full)}
                  >
                    {content}
                  </button>
                ) : (
                  content
                )}
              </span>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="chat-app">
      <header className="chat-header">
        <div>
          <div className="chat-title-row">
            <img src={logo} alt="inSwitch logo" className="chat-logo" />
            <p className="chat-title">inSwitch Agent</p>
          </div>
        </div>
        <div className="status-pill">
          <span className={`status-dot ${isSending ? 'busy' : 'ready'}`} />
          {isSending ? 'Thinking…' : 'Ready'}
        </div>
      </header>

      <main className="chat-panels">
        <section className="panel logs-panel">
          <div className="panel-header">
            <div>
              <p className="panel-title">Agent Logs</p>
              <p className="panel-subtitle">Live stream from /logs/stream</p>
            </div>
            <div className={`log-status ${logStatus}`}>
              <span className="status-dot" />
              {logStatus === 'connected' ? 'Live' : 'Reconnecting'}
            </div>
          </div>
          <div className="log-list" ref={logListRef}>
            {logs.length === 0 ? (
              <p className="empty-state">Waiting for log events…</p>
            ) : (
              logs.map(renderLogEntry)
            )}
          </div>
        </section>

        <div className="chat-column">
          <section className="panel chat-panel">
            <div className="message-list" ref={listRef}>
              {messages.map((message) => (
                <div key={message.id} className={`message-row ${message.role}`}>
                  <div className="message-bubble">
                    <p>{message.text}</p>
                  </div>
                </div>
              ))}
            </div>
            {error && <div className="error-banner">{error}</div>}
          </section>

          <footer className="chat-input">
            <div className="input-shell">
              <textarea
                ref={inputRef}
                placeholder="Type a message…"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
              />
              <button
                type="button"
                className="send-button"
                onClick={sendMessage}
                disabled={!canSend}
              >
                Send
              </button>
            </div>
          </footer>
        </div>

        <section className="panel graph-panel">
          <div className="panel-header">
            <div>
              <p className="panel-title">Agent Graph</p>
            </div>
          </div>
          <div className="graph-canvas">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              fitView
            >
              <MiniMap />
              <Controls />
              <Background gap={18} size={1} />
            </ReactFlow>
          </div>
        </section>
      </main>

      {selectedValue !== null && (
        <div className="log-modal-overlay" onClick={() => setSelectedValue(null)}>
          <div className="log-modal" onClick={(event) => event.stopPropagation()}>
            <div className="log-modal-header">
              <span>Full Value</span>
              <button
                type="button"
                className="log-modal-close"
                onClick={() => setSelectedValue(null)}
              >
                Close
              </button>
            </div>
            <div className="log-modal-body">
              <pre>{selectedValue}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
