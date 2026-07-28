"use client";

import { useState, useRef, useEffect } from "react";
import { Bot, Send, User, Cpu, Terminal, AlertTriangle, Loader2, Trash2 } from "lucide-react";
import Image from "next/image";

const API_URL = process.env.NEXT_PUBLIC_WEB_AGENT_URL || "http://localhost:8002";

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  reasoning?: string;
  toolType?: string;
  toolName?: string;
  arguments?: Record<string, unknown>;
  executionOutput?: string;
  timestamp: Date;
  isLoading?: boolean;
}

export default function AgentPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || isThinking) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsThinking(true);

    // Add a loading placeholder
    const loadingId = crypto.randomUUID();
    setMessages((prev) => [
      ...prev,
      {
        id: loadingId,
        role: "agent",
        content: "",
        timestamp: new Date(),
        isLoading: true,
      },
    ]);

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: trimmed }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();

      const agentMsg: ChatMessage = {
        id: loadingId,
        role: "agent",
        content: data.agent_response,
        reasoning: data.reasoning,
        toolType: data.tool_type,
        toolName: data.tool_name,
        arguments: data.arguments,
        executionOutput: data.execution_output,
        timestamp: new Date(),
      };

      setMessages((prev) => prev.map((m) => (m.id === loadingId ? agentMsg : m)));
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Failed to reach the agent";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === loadingId
            ? {
                ...m,
                content: `Error: ${errorMessage}`,
                isLoading: false,
              }
            : m
        )
      );
    } finally {
      setIsThinking(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-6 py-4 border-b border-[rgb(var(--border))] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-10 h-10 rounded-full overflow-hidden shadow-lg">
              <Image
                src="/agent-icon.jpg"
                alt="AI Agent"
                width={40}
                height={40}
                className="object-cover"
              />
            </div>
            <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-emerald-400 rounded-full border-2 border-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-[rgb(var(--foreground))]">
              Drake AI Agent
            </h1>
            <p className="text-xs text-[rgb(var(--muted-foreground))]">
              Powered by Ollama · MCP + CLI Tools
            </p>
          </div>
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => setMessages([])}
            className="text-slate-400 hover:text-rose-500 transition-colors p-2"
            title="Clear Chat"
            aria-label="Clear Chat"
          >
            <Trash2 className="w-5 h-5" />
          </button>
        )}
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center space-y-4 opacity-60">
            <div className="w-16 h-16 rounded-full overflow-hidden shadow-sm border border-[rgb(var(--border))]">
              <Image
                src="/agent-icon.jpg"
                alt="AI Agent"
                width={64}
                height={64}
                className="object-cover"
              />
            </div>
            <div>
              <p className="text-[rgb(var(--foreground))] font-medium text-lg">
                How can I help you today?
              </p>
              <p className="text-sm text-[rgb(var(--muted-foreground))] mt-1 max-w-md">
                Ask me to execute workflows, check platform health, view audit logs, or manage server configurations.
              </p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-4 w-full max-w-lg">
              {[
                "Show me pending workflows",
                "What is the platform health status?",
                "Show audit log",
                "Run diagnostics",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => {
                    setInput(suggestion);
                    inputRef.current?.focus();
                  }}
                  className="text-left px-4 py-2.5 rounded-xl border border-[rgb(var(--border))] text-sm text-[rgb(var(--muted-foreground))] hover:border-emerald-300 hover:text-emerald-600 hover:bg-emerald-50/50 transition-all cursor-pointer"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
            {msg.role === "agent" && (
              <div className="shrink-0 w-8 h-8 rounded-full overflow-hidden mt-1 shadow-sm border border-[rgb(var(--border))]">
                <Image
                  src="/agent-icon.jpg"
                  alt="AI Agent"
                  width={32}
                  height={32}
                  className="object-cover"
                />
              </div>
            )}

            <div
              className={`max-w-[75%] ${
                msg.role === "user"
                  ? "bg-white text-[rgb(var(--foreground))] border border-[rgb(var(--border))] rounded-2xl rounded-br-md px-4 py-3 shadow-sm"
                  : "space-y-3"
              }`}
            >
              {msg.isLoading ? (
                <div className="flex items-center gap-2 text-[rgb(var(--muted-foreground))] bg-[rgb(var(--muted))]/50 rounded-2xl rounded-bl-md px-4 py-3">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="text-sm">Agent is thinking...</span>
                </div>
              ) : msg.role === "user" ? (
                <p className="text-sm leading-relaxed">{msg.content}</p>
              ) : (
                <>
                  {/* Agent Response */}
                  <div className="bg-white rounded-2xl rounded-bl-md px-4 py-3 border border-[rgb(var(--border))] shadow-sm">
                    <p className="text-sm text-[rgb(var(--foreground))] leading-relaxed">
                      {msg.content}
                    </p>
                  </div>

                  {/* Reasoning (Collapsible) */}
                  {msg.reasoning && (
                    <details className="group">
                      <summary className="flex items-center gap-1.5 text-xs text-[rgb(var(--muted-foreground))] cursor-pointer hover:text-[rgb(var(--foreground))] transition-colors list-none [&::-webkit-details-marker]:hidden">
                        <Cpu className="w-3 h-3" />
                        Internal Reasoning
                      </summary>
                      <div className="mt-1.5 ml-4.5 px-3 py-2 bg-amber-50 border border-amber-200/60 rounded-lg text-xs text-amber-800 leading-relaxed">
                        {msg.reasoning}
                      </div>
                    </details>
                  )}

                  {/* Tool Execution Details */}
                  {msg.toolType && msg.toolType !== "none" && msg.toolName?.toUpperCase() !== "NONE" && (
                    <div className="bg-gray-50 rounded-xl border border-[rgb(var(--border))] overflow-hidden">
                      <div className="flex items-center gap-2 px-3 py-2 bg-gray-100/80 border-b border-[rgb(var(--border))]">
                        <Terminal className="w-3.5 h-3.5 text-emerald-600" />
                        <span className="text-xs font-medium text-[rgb(var(--foreground))]">
                          Tool: {msg.toolName}
                        </span>
                        <span
                          className={`ml-auto text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full ${
                            msg.toolType === "mcp"
                              ? "bg-cyan-100 text-cyan-700"
                              : "bg-violet-100 text-violet-700"
                          }`}
                        >
                          {msg.toolType}
                        </span>
                      </div>
                      {msg.arguments && Object.keys(msg.arguments).length > 0 && (
                        <div className="px-3 py-2 border-b border-[rgb(var(--border))]">
                          <p className="text-[10px] font-medium text-[rgb(var(--muted-foreground))] uppercase tracking-wider mb-1">
                            Arguments
                          </p>
                          <pre className="text-xs text-[rgb(var(--foreground))] font-mono bg-white rounded-md px-2 py-1.5 overflow-x-auto">
                            {JSON.stringify(msg.arguments, null, 2)}
                          </pre>
                        </div>
                      )}
                      {msg.executionOutput && (
                        <div className="px-3 py-2">
                          <p className="text-[10px] font-medium text-[rgb(var(--muted-foreground))] uppercase tracking-wider mb-1">
                            Execution Output
                          </p>
                          <pre className="text-xs text-[rgb(var(--foreground))] font-mono bg-white rounded-md px-2 py-1.5 overflow-x-auto max-h-64 overflow-y-auto whitespace-pre-wrap">
                            {msg.executionOutput}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>

            {msg.role === "user" && (
              <div className="shrink-0 w-8 h-8 rounded-full overflow-hidden mt-1 shadow-sm border border-[rgb(var(--border))]">
                <Image
                  src="/userprofile.png"
                  alt="User Profile"
                  width={32}
                  height={32}
                  className="object-cover"
                />
              </div>
            )}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="shrink-0 px-6 py-4 border-t border-[rgb(var(--border))] bg-white/50">
        <div className="flex items-center gap-3">
          <div className="flex-1 relative">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your command..."
              disabled={isThinking}
              className="w-full px-4 py-3 pr-12 rounded-xl border border-[rgb(var(--border))] bg-white text-sm text-[rgb(var(--foreground))] placeholder-[rgb(var(--muted-foreground))] focus:outline-none focus:ring-2 focus:ring-emerald-400/40 focus:border-emerald-400 transition-all disabled:opacity-50"
            />
          </div>
          <button
            onClick={sendMessage}
            disabled={isThinking || !input.trim()}
            className="w-11 h-11 rounded-xl bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center text-white shadow-lg shadow-emerald-500/20 hover:shadow-emerald-500/40 transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none cursor-pointer"
          >
            {isThinking ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
