import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { prism } from 'react-syntax-highlighter/dist/esm/styles/prism';
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

const normalizeCodeLanguage = (className?: string) => {
  const match = /language-([a-zA-Z0-9_-]+)/.exec(className ?? '');
  if (!match) return null;
  const lang = match[1].toLowerCase();
  if (lang === 'py') return 'python';
  if (lang === 'yml') return 'yaml';
  return lang;
};

const detectCodeLanguage = (code: string) => {
  const source = code.trim();
  if (
    source.includes('import urllib') ||
    source.includes('def ') ||
    source.includes('print(') ||
    source.includes('json.loads(')
  ) {
    return 'python';
  }
  if (
    source.includes('schema_version:') ||
    source.includes('workloads:') ||
    /\n\s*-\s+name:/.test(source)
  ) {
    return 'yaml';
  }
  return 'text';
};

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
  const [selectedValue, setSelectedValue] = useState<unknown | null>(null);
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
  const buildNodeId = useCallback((kind: GraphKind, name: string) => `${kind}:${name}`, []);

  const canSend = useMemo(() => input.trim().length > 0 && !isSending, [input, isSending]);

  const renderMarkdown = useCallback(
    (content: string, className: string) => (
      <div className={className}>
        <ReactMarkdown
          components={{
            code({ inline, className: codeClassName, children, ...props }: any) {
              if (inline) {
                return (
                  <code className={codeClassName} {...props}>
                    {children}
                  </code>
                );
              }

              const language = normalizeCodeLanguage(codeClassName);
              const text = String(children).replace(/\n$/, '');

              if (!language) {
                return (
                  <pre>
                    <code className={codeClassName} {...props}>
                      {children}
                    </code>
                  </pre>
                );
              }

              return (
                <SyntaxHighlighter
                  PreTag="div"
                  language={language}
                  style={prism}
                  wrapLongLines
                  customStyle={{ margin: 0, borderRadius: '0.75rem', padding: '0.75rem 0.85rem' }}
                >
                  {text}
                </SyntaxHighlighter>
              );
            }
          }}
        >
          {content}
        </ReactMarkdown>
      </div>
    ),
    []
  );

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
      const id = buildNodeId(kind, name);
      const existing = nodesRef.current.find((node) => node.id === id);
      if (existing) {
        highlightNode(id);
        return;
      }
      const position = nextPosition();
      const newNode: Node<GraphNodeData> = {
        id,
        position,
        data: { label: name, kind },
        type: 'default',
        className: buildNodeClass(kind, false)
      };
      setNodes((prev) => [...prev, newNode]);
    },
    [buildNodeId, highlightNode, nextPosition, setNodes]
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
          if (payload.agent) {
            ensureEdge(
              buildNodeId('agent', payload.created_by),
              buildNodeId('agent', payload.agent),
              'creates'
            );
          }
        }
        return;
      }

      if (event === 'skill_loaded') {
        ensureNode(payload.agent, 'agent');
        ensureNode(payload.skill, 'skill');
        if (payload.agent && payload.skill) {
          ensureEdge(
            buildNodeId('agent', payload.agent),
            buildNodeId('skill', payload.skill),
            'skill'
          );
        }
        return;
      }

      if (event === 'tool_invocation') {
        ensureNode(payload.agent, 'agent');
        ensureNode(payload.tool, 'tool');
        if (payload.agent && payload.tool) {
          ensureEdge(
            buildNodeId('agent', payload.agent),
            buildNodeId('tool', payload.tool),
            'calls'
          );
        }
        return;
      }

      if (event === 'tool_result') {
        ensureNode(payload.agent, 'agent');
        ensureNode(payload.tool, 'tool');
        if (payload.agent && payload.tool) {
          ensureEdge(
            buildNodeId('tool', payload.tool),
            buildNodeId('agent', payload.agent),
            'returns'
          );
        }
        return;
      }

      if (event === 'agent_message') {
        ensureNode(payload.from, 'agent');
        ensureNode(payload.to, 'agent');
        if (payload.from && payload.to) {
          ensureEdge(
            buildNodeId('agent', payload.from),
            buildNodeId('agent', payload.to),
            'sends'
          );
        }
      }
    },
    [buildNodeId, ensureEdge, ensureNode]
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

  const safeStringify = (value: unknown, spacing = 0) => {
    try {
      return JSON.stringify(value, null, spacing);
    } catch {
      return null;
    }
  };

  const isHttpEnvelope = (value: unknown): value is Record<string, unknown> => {
    if (!value || typeof value !== 'object') return false;
    const record = value as Record<string, unknown>;
    return 'status_code' in record && 'headers' in record && 'body' in record;
  };

  const parseMaybeJsonString = (value: unknown): unknown => {
    if (typeof value !== 'string') return value;
    try {
      return JSON.parse(value);
    } catch {
      return value;
    }
  };

  const normalizeHttpEnvelope = (value: unknown) => {
    if (!isHttpEnvelope(value)) return null;
    const record = value as Record<string, unknown>;
    const rawHeaders = record.headers;
    const headers =
      rawHeaders && typeof rawHeaders === 'object'
        ? Object.entries(rawHeaders as Record<string, unknown>).reduce<Record<string, string>>(
            (acc, [key, val]) => {
              acc[key] = String(val);
              return acc;
            },
            {}
          )
        : {};

    return {
      statusCode: String(record.status_code ?? ''),
      headers,
      body: parseMaybeJsonString(record.body)
    };
  };

  const getStatusTone = (statusCode: string) => {
    const code = Number.parseInt(statusCode, 10);
    if (Number.isNaN(code)) return 'neutral';
    if (code >= 400) return 'error';
    if (code >= 300) return 'warn';
    return 'ok';
  };

  const parseJsonValue = (value: unknown) => {
    if (typeof value === 'string') {
      try {
        return parseJsonValue(JSON.parse(value));
      } catch {
        return { type: 'plain' as const, text: value };
      }
    }
    if (value !== null && typeof value === 'object') {
      return { type: 'json' as const, data: value };
    }
    return { type: 'plain' as const, text: String(value) };
  };

  const highlightJson = (json: string) => {
    const escaped = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return escaped.replace(
      /("(\\u[a-fA-F0-9]{4}|\\[^u]|[^\\"])*"(?:\\s*:)?|\\b(true|false|null)\\b|-?\\d+(?:\\.\\d*)?(?:[eE][+\\-]?\\d+)?)/g,
      (match) => {
        let cls = 'json-number';
        if (match.startsWith('"')) {
          cls = match.endsWith(':') ? 'json-key' : 'json-string';
        } else if (match === 'true' || match === 'false') {
          cls = 'json-boolean';
        } else if (match === 'null') {
          cls = 'json-null';
        }
        return `<span class="${cls}">${match}</span>`;
      }
    );
  };

  const renderJsonViewer = (data: unknown) => {
    const pretty = safeStringify(data, 2);
    if (!pretty) return null;
    const highlighted = highlightJson(pretty);
    const lines = highlighted.split('\n');
    return (
      <div className="json-viewer">
        {lines.map((line, idx) => (
          <div key={idx} className="json-line">
            <span className="json-line-no">{idx + 1}</span>
            <span
              className="json-line-code"
              dangerouslySetInnerHTML={{ __html: line.length === 0 ? '&nbsp;' : line }}
            />
          </div>
        ))}
      </div>
    );
  };

  const renderStructuredResult = (data: unknown) => {
    if (!data || typeof data !== 'object') return null;
    const record = data as Record<string, unknown>;
    if (typeof record.code !== 'string') return null;

    const language = detectCodeLanguage(record.code);
    const rest = { ...record };
    delete rest.code;
    const hasRest = Object.keys(rest).length > 0;

    return (
      <div className="structured-result">
        <div className="structured-result-header">Code</div>
        <SyntaxHighlighter
          PreTag="div"
          language={language}
          style={prism}
          wrapLongLines
          customStyle={{ margin: 0, borderRadius: '0.8rem', padding: '0.85rem 0.95rem' }}
        >
          {record.code}
        </SyntaxHighlighter>
        {hasRest && (
          <div className="structured-result-meta">
            <div className="structured-result-header">Metadata</div>
            {renderJsonViewer(rest)}
          </div>
        )}
      </div>
    );
  };

  const renderCommandOutput = (data: unknown) => {
    if (!data || typeof data !== 'object') return null;
    const record = data as Record<string, unknown>;
    const hasStdout = typeof record.stdout === 'string';
    const hasStderr = typeof record.stderr === 'string';
    const hasExitCode = typeof record.exit_code === 'number' || typeof record.exit_code === 'string';
    if (!hasStdout && !hasStderr && !hasExitCode) return null;

    return (
      <div className="command-result">
        {hasExitCode && (
          <div className="command-result-header">
            Exit code:{' '}
            <span className={`command-exit ${String(record.exit_code) === '0' ? 'ok' : 'error'}`}>
              {String(record.exit_code)}
            </span>
          </div>
        )}
        {hasStdout && (record.stdout as string).length > 0 && (
          <div className="command-block">
            <div className="command-label">stdout</div>
            <pre className="command-output">{record.stdout as string}</pre>
          </div>
        )}
        {hasStderr && (record.stderr as string).length > 0 && (
          <div className="command-block command-block-error">
            <div className="command-label">stderr</div>
            <pre className="command-output">{record.stderr as string}</pre>
          </div>
        )}
      </div>
    );
  };

  const renderValueDetails = (value: unknown) => {
    const envelope = normalizeHttpEnvelope(value);
    if (envelope) {
      const contentType = envelope.headers['content-type'];
      const date = envelope.headers.date;
      const tone = getStatusTone(envelope.statusCode);
      return (
        <div className="http-envelope-view">
          <div className="http-envelope-meta">
            <span className={`http-meta-pill http-meta-pill-${tone}`}>
              HTTP {envelope.statusCode || 'unknown'}
            </span>
            {contentType && <span className="http-meta-pill">{contentType}</span>}
            {date && <span className="http-meta-pill">{date}</span>}
          </div>
          <div className="http-envelope-body">{renderValueDetails(envelope.body)}</div>
        </div>
      );
    }

    const parsed = parseJsonValue(value);
    if (parsed.type === 'json') {
      const structured = renderStructuredResult(parsed.data);
      if (structured) {
        return structured;
      }
      const commandOutput = renderCommandOutput(parsed.data);
      if (commandOutput) {
        return commandOutput;
      }
      const jsonViewer = renderJsonViewer(parsed.data);
      if (jsonViewer) {
        return jsonViewer;
      }
    }

    return (
      renderMarkdown(parsed.type === 'plain' ? parsed.text : String(value), 'markdown-content modal-markdown-content')
    );
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

    const classifyParam = (key: string) => {
      const normalized = key.toLowerCase();
      if (normalized === 'agent' || normalized === 'from' || normalized === 'to' || normalized === 'created_by') {
        return 'agent';
      }
      if (normalized === 'tool') {
        return 'tool';
      }
      if (normalized === 'skill') {
        return 'skill';
      }
      return 'default';
    };

    const formatValue = (value: any, key: string) => {
      const previewLimit = 18;
      const envelope = normalizeHttpEnvelope(parseMaybeJsonString(value));
      if (envelope) {
        const contentType = envelope.headers['content-type'];
        const tone = getStatusTone(envelope.statusCode);
        return {
          display: contentType ? `${envelope.statusCode} ${contentType}` : envelope.statusCode,
          raw: parseMaybeJsonString(value),
          truncated: false,
          expandable: true,
          tone
        };
      }

      const parsed = parseJsonValue(value);
      const displayValue = parsed.type === 'json' ? parsed.data : parsed.text;

      if (displayValue === null || displayValue === undefined) {
        return {
          display: String(displayValue),
          raw: displayValue,
          truncated: false,
          expandable: false,
          tone: 'neutral'
        };
      }
      if (typeof displayValue === 'string') {
        const isErrorField = key.toLowerCase().includes('error');
        const tone = isErrorField && displayValue.trim().length > 0 ? 'error' : 'neutral';
        if (displayValue.length > previewLimit) {
          return {
            display: displayValue.slice(0, previewLimit),
            raw: displayValue,
            truncated: true,
            expandable: false,
            tone
          };
        }
        return { display: displayValue, raw: displayValue, truncated: false, expandable: false, tone };
      }
      if (typeof displayValue === 'object') {
        const json = safeStringify(displayValue) ?? String(displayValue);
        if (json.length > previewLimit) {
          return {
            display: json.slice(0, previewLimit),
            raw: displayValue,
            truncated: true,
            expandable: false,
            tone: 'neutral'
          };
        }
        return { display: json, raw: displayValue, truncated: false, expandable: false, tone: 'neutral' };
      }
      const text = String(displayValue);
      return { display: text, raw: displayValue, truncated: false, expandable: false, tone: 'neutral' };
    };

    return (
      <div key={`${entry}-${index}`} className="log-card">
        <div className="log-card-header">
          <span className="log-event">{eventType}</span>
          {timestamp && <span className="log-ts">{timestamp}</span>}
        </div>
        <div className="log-params">
          {Object.entries(params).map(([key, value]) => {
            const formatted = formatValue(value, key);
            const content = (
              <span className={`log-value ${formatted.tone === 'error' ? 'log-value-error' : ''}`}>
                {formatted.display}
                {formatted.truncated && <span className="log-ellipsis">…</span>}
              </span>
            );
            return (
              <span key={key} className={`log-param log-param-${classifyParam(key)}`}>
                <span className="log-key">{key}:</span>
                {formatted.truncated || formatted.expandable ? (
                  <button
                    type="button"
                    className="log-value-button"
                    onClick={() => setSelectedValue(formatted.raw)}
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
              <p className="panel-subtitle">
                Live stream from /logs/stream. Agent = green, Tool = blue, Skill = amber.
              </p>
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
                    {message.role === 'agent' ? (
                      renderMarkdown(message.text, 'markdown-content message-markdown-content')
                    ) : (
                      <p>{message.text}</p>
                    )}
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
              {renderValueDetails(selectedValue)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default App;
