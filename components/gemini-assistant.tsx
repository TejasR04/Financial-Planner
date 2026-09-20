"use client";

import {
  Fragment,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  Bot,
  CircleAlert,
  History,
  Plus,
  Send,
  Sparkles,
  Trash2,
  UserRound,
  Wrench,
} from "lucide-react";
import {
  api,
  ApiError,
  type ApiAgentChatResponse,
  type ApiAgentConversation,
} from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { cn } from "@/lib/utils";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools?: ApiAgentChatResponse["tool_calls"];
};

const SUGGESTIONS = [
  "Analyze my current financial plan and identify the three most important things to address.",
  "Can I retire at my saved target age based on the information in Meridian?",
  "How should I use my current monthly surplus?",
];
const CHAT_INACTIVITY_MS = 30 * 60 * 1000;

function temporaryId(role: ChatMessage["role"]) {
  return `${role}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function renderInlineMarkdown(value: string): ReactNode[] {
  return value
    .split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g)
    .map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={`${part}-${index}`} className="font-semibold">
            {renderInlineMarkdown(part.slice(2, -2))}
          </strong>
        );
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code
            key={`${part}-${index}`}
            className="rounded bg-muted px-1 py-0.5 font-mono text-[0.92em]"
          >
            {part.slice(1, -1)}
          </code>
        );
      }
      if (part.startsWith("*") && part.endsWith("*")) {
        return <em key={`${part}-${index}`}>{part.slice(1, -1)}</em>;
      }
      return <Fragment key={`${part}-${index}`}>{part}</Fragment>;
    });
}

function AssistantContent({ content }: { content: string }) {
  return (
    <div className="space-y-1.5">
      {content.split("\n").map((line, index) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={`space-${index}`} className="h-1" />;
        if (trimmed === "---") {
          return <div key={`rule-${index}`} className="my-2 border-t border-border" />;
        }
        if (trimmed.startsWith("### ")) {
          return (
            <p key={`heading-${index}`} className="pt-1 font-semibold text-foreground">
              {renderInlineMarkdown(trimmed.slice(4))}
            </p>
          );
        }

        const ordered = /^(\d+)\.\s+(.*)$/.exec(trimmed);
        if (ordered) {
          return (
            <div key={`ordered-${index}`} className="flex gap-2">
              <span className="w-4 shrink-0 font-mono text-muted-foreground">{ordered[1]}.</span>
              <p>{renderInlineMarkdown(ordered[2])}</p>
            </div>
          );
        }

        const bullet = /^[*-]\s+(.*)$/.exec(trimmed);
        if (bullet) {
          return (
            <div key={`bullet-${index}`} className="flex gap-2 pl-1">
              <span className="text-muted-foreground">•</span>
              <p>{renderInlineMarkdown(bullet[1])}</p>
            </div>
          );
        }

        return <p key={`line-${index}`}>{renderInlineMarkdown(trimmed)}</p>;
      })}
    </div>
  );
}

function LiveGeminiAssistant() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversations, setConversations] = useState<ApiAgentConversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const lastActivityRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.agent
      .conversations()
      .then((history) => {
        if (!cancelled) {
          setConversations(history);
        }
      })
      .catch((cause) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Could not load chat history.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function refreshConversations() {
    const history = await api.agent.conversations();
    setConversations(history);
  }

  async function openConversation(conversationId: string) {
    if (sending || loadingConversation) return;
    setLoadingConversation(true);
    setError(null);
    try {
      const history = await api.agent.conversationMessages(conversationId);
      setMessages(
        history.map((message) => ({
          id: message.id,
          role: message.role,
          content: message.content,
        })),
      );
      setActiveConversationId(conversationId);
      lastActivityRef.current = Date.now();
      setShowHistory(false);
      setConfirmClear(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not open that chat.");
    } finally {
      setLoadingConversation(false);
    }
  }

  function startNewChat() {
    if (sending) return;
    setMessages([]);
    setActiveConversationId(null);
    lastActivityRef.current = null;
    setInput("");
    setError(null);
    setConfirmClear(false);
    setShowHistory(false);
  }

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    if (typeof container.scrollTo === "function") {
      container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
    } else {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages, sending]);

  async function sendMessage(message: string) {
    const trimmed = message.trim();
    if (!trimmed || sending) return;

    const userMessage: ChatMessage = {
      id: temporaryId("user"),
      role: "user",
      content: trimmed,
    };
    const conversationTimedOut = Boolean(
      activeConversationId &&
        lastActivityRef.current &&
        Date.now() - lastActivityRef.current >= CHAT_INACTIVITY_MS,
    );
    const conversationId = conversationTimedOut ? null : activeConversationId;
    if (conversationTimedOut) {
      setMessages([userMessage]);
      setActiveConversationId(null);
    } else {
      setMessages((current) => [...current, userMessage]);
    }
    setInput("");
    setError(null);
    setSending(true);

    try {
      const result = await api.agent.chat(trimmed, conversationId);
      setActiveConversationId(result.conversation_id);
      lastActivityRef.current = Date.now();
      setMessages((current) => [
        ...current,
        {
          id: temporaryId("assistant"),
          role: "assistant",
          content: result.reply || "Gemini returned an empty response.",
          tools: result.tool_calls,
        },
      ]);
      void refreshConversations().catch(() => {
        setError("The response was saved, but chat history could not refresh.");
      });
    } catch (cause) {
      setMessages((current) => current.filter((message) => message.id !== userMessage.id));
      setInput(trimmed);
      setError(
        cause instanceof ApiError
          ? cause.message
          : "Gemini could not complete the analysis. Please try again.",
      );
    } finally {
      setSending(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void sendMessage(input);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(input);
    }
  }

  async function clearConversation() {
    if (!activeConversationId) {
      startNewChat();
      return;
    }
    try {
      await api.agent.deleteConversation(activeConversationId);
      startNewChat();
      await refreshConversations();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete the chat.");
    }
  }

  async function deleteConversation(conversationId: string) {
    try {
      await api.agent.deleteConversation(conversationId);
      if (conversationId === activeConversationId) startNewChat();
      await refreshConversations();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete the chat.");
    }
  }

  return (
    <section className="overflow-hidden rounded-lg border border-primary/25 bg-card shadow-sm">
      <div className="flex flex-col gap-3 border-b border-border bg-primary/[0.035] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Sparkles className="size-4" />
          </span>
          <div>
            <h2 className="text-[14px] font-semibold tracking-tight text-foreground">
              Gemini financial assistant
            </h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Uses summary data by default; relevant transaction details are included only when you ask for them
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-1.5">
          <Button size="xs" variant="ghost" onClick={() => setShowHistory((current) => !current)}>
            <History />
            History{conversations.length > 0 ? ` (${conversations.length})` : ""}
          </Button>
          {(activeConversationId || messages.length > 0) && (
            <Button size="xs" variant="ghost" onClick={startNewChat} disabled={sending}>
              <Plus />
              New chat
            </Button>
          )}
          {messages.length > 0 && (confirmClear ? (
            <div className="flex items-center gap-1.5">
              <span className="mr-1 text-[11px] text-muted-foreground">Delete this chat?</span>
              <Button size="xs" variant="ghost" onClick={() => setConfirmClear(false)}>
                Cancel
              </Button>
              <Button size="xs" variant="destructive" onClick={() => void clearConversation()}>
                Delete
              </Button>
            </div>
          ) : (
            <Button size="xs" variant="ghost" onClick={() => setConfirmClear(true)}>
              <Trash2 />
              Delete chat
            </Button>
          ))}
        </div>
      </div>

      {showHistory && (
        <div className="border-b border-border bg-muted/15 px-4 py-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold text-foreground">Previous chats</p>
            <Button size="xs" variant="outline" onClick={startNewChat} disabled={sending}>
              <Plus />
              New chat
            </Button>
          </div>
          {conversations.length === 0 ? (
            <p className="py-3 text-center text-xs text-muted-foreground">No previous chats yet.</p>
          ) : (
            <div className="max-h-52 space-y-1 overflow-y-auto">
              {conversations.map((conversation) => (
                <div
                  key={conversation.id}
                  className={cn(
                    "flex items-center gap-2 rounded-md border px-2 py-1.5",
                    conversation.id === activeConversationId
                      ? "border-primary/35 bg-primary/5"
                      : "border-transparent hover:bg-accent",
                  )}
                >
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => void openConversation(conversation.id)}
                  >
                    <span className="block truncate text-xs font-medium text-foreground">
                      {conversation.title}
                    </span>
                    <span className="text-[10px] text-muted-foreground">
                      {new Date(conversation.updated_at).toLocaleDateString()} · {conversation.message_count} messages
                    </span>
                  </button>
                  <Button
                    type="button"
                    size="icon-xs"
                    variant="ghost"
                    aria-label={`Delete ${conversation.title}`}
                    onClick={() => void deleteConversation(conversation.id)}
                  >
                    <Trash2 />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div ref={scrollRef} className="max-h-[460px] min-h-64 overflow-y-auto p-4">
        {loadingHistory || loadingConversation ? (
          <div className="flex min-h-48 items-center justify-center text-[13px] text-muted-foreground">
            Loading chat…
          </div>
        ) : messages.length === 0 ? (
          <div className="mx-auto flex min-h-48 max-w-2xl flex-col items-center justify-center text-center">
            <span className="flex size-10 items-center justify-center rounded-full bg-primary/10">
              <Bot className="size-5 text-primary" />
            </span>
            <h3 className="mt-3 text-sm font-semibold text-foreground">
              Ask about your actual financial plan
            </h3>
            <p className="mt-1 max-w-lg text-[13px] leading-relaxed text-muted-foreground">
              Gemini can explain your saved balances and assumptions, then call Meridian’s
              calculation tools for projections, allocation, debt, cash flow, and taxes.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((suggestion, index) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => void sendMessage(suggestion)}
                  className="rounded-full border border-border bg-background px-3 py-1.5 text-left text-[12px] text-foreground transition-colors hover:border-primary/40 hover:bg-accent"
                >
                  {index === 0 ? "Analyze my plan" : index === 1 ? "Retirement readiness" : "Use my surplus"}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => {
              const assistant = message.role === "assistant";
              const Icon = assistant ? Bot : UserRound;
              return (
                <div
                  key={message.id}
                  className={cn("flex gap-2.5", !assistant && "flex-row-reverse")}
                >
                  <span
                    className={cn(
                      "flex size-7 shrink-0 items-center justify-center rounded-full",
                      assistant
                        ? "bg-primary/10 text-primary"
                        : "bg-muted text-muted-foreground",
                    )}
                  >
                    <Icon className="size-3.5" />
                  </span>
                  <div
                    className={cn(
                      "max-w-[88%] rounded-xl px-3.5 py-2.5 text-[13px] leading-relaxed",
                      assistant
                        ? "rounded-tl-sm border border-border bg-background text-foreground"
                        : "rounded-tr-sm bg-primary text-primary-foreground",
                    )}
                  >
                    {assistant ? (
                      <AssistantContent content={message.content} />
                    ) : (
                      <p className="whitespace-pre-wrap">{message.content}</p>
                    )}
                    {assistant && message.tools && message.tools.length > 0 && (
                      <div className="mt-2.5 flex flex-wrap gap-1.5 border-t border-border pt-2">
                        {message.tools.map((tool, index) => (
                          <span
                            key={`${tool.tool}-${index}`}
                            className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
                          >
                            <Wrench className="size-2.5" />
                            {tool.tool}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {sending && (
              <div className="flex gap-2.5">
                <span className="flex size-7 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <Bot className="size-3.5" />
                </span>
                <div className="rounded-xl rounded-tl-sm border border-border bg-background px-3.5 py-2.5 text-[13px] text-muted-foreground">
                  Analyzing your current data…
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="mx-4 mb-3 flex items-start gap-2 rounded-md border border-destructive/25 bg-destructive/5 px-3 py-2 text-[12px] text-destructive">
          <CircleAlert className="mt-0.5 size-3.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="border-t border-border bg-muted/20 p-3">
        <div className="flex items-end gap-2 rounded-lg border border-border bg-background p-1.5 focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/10">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Gemini about your plan…"
            rows={2}
            maxLength={4000}
            disabled={sending || loadingHistory || loadingConversation}
            className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-2 py-1.5 text-[13px] text-foreground outline-none placeholder:text-muted-foreground"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || sending || loadingHistory || loadingConversation}
            aria-label="Send message"
          >
            <Send />
          </Button>
        </div>
        <p className="mt-1.5 px-1 text-[10px] text-muted-foreground">
          Enter to send · Shift+Enter for a new line · Verify important financial decisions
        </p>
      </form>
    </section>
  );
}

export function GeminiAssistant() {
  const { isDemo } = useAuth();
  return isDemo ? <div className="rounded-lg border border-border p-6 text-sm text-muted-foreground">Gemini assistant is disabled in demo mode.</div> : <LiveGeminiAssistant />;
}
