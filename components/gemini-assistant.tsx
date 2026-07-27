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
  Eraser,
  Send,
  Sparkles,
  UserRound,
  Wrench,
} from "lucide-react";
import { api, ApiError, type ApiAgentChatResponse } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
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

export function GeminiAssistant() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    api.agent
      .history()
      .then((history) => {
        if (!cancelled) {
          setMessages(
            history.map((message) => ({
              id: message.id,
              role: message.role,
              content: message.content,
            })),
          );
        }
      })
      .catch((cause) => {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Could not load the conversation.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, sending]);

  async function sendMessage(message: string) {
    const trimmed = message.trim();
    if (!trimmed || sending) return;

    const userMessage: ChatMessage = {
      id: temporaryId("user"),
      role: "user",
      content: trimmed,
    };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setError(null);
    setSending(true);

    try {
      const result = await api.agent.chat(trimmed);
      setMessages((current) => [
        ...current,
        {
          id: temporaryId("assistant"),
          role: "assistant",
          content: result.reply || "Gemini returned an empty response.",
          tools: result.tool_calls,
        },
      ]);
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
    try {
      await api.agent.clearHistory();
      setMessages([]);
      setError(null);
      setConfirmClear(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not clear the conversation.");
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
              Uses your current Meridian data and deterministic calculation tools
            </p>
          </div>
        </div>

        {messages.length > 0 &&
          (confirmClear ? (
            <div className="flex items-center gap-1.5">
              <span className="mr-1 text-[11px] text-muted-foreground">Clear saved history?</span>
              <Button size="xs" variant="ghost" onClick={() => setConfirmClear(false)}>
                Cancel
              </Button>
              <Button size="xs" variant="destructive" onClick={() => void clearConversation()}>
                Clear
              </Button>
            </div>
          ) : (
            <Button size="xs" variant="ghost" onClick={() => setConfirmClear(true)}>
              <Eraser />
              Clear conversation
            </Button>
          ))}
      </div>

      <div ref={scrollRef} className="max-h-[460px] min-h-64 overflow-y-auto p-4">
        {loadingHistory ? (
          <div className="flex min-h-48 items-center justify-center text-[13px] text-muted-foreground">
            Loading your conversation…
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
            disabled={sending || loadingHistory}
            className="max-h-32 min-h-10 flex-1 resize-none bg-transparent px-2 py-1.5 text-[13px] text-foreground outline-none placeholder:text-muted-foreground"
          />
          <Button
            type="submit"
            size="icon"
            disabled={!input.trim() || sending || loadingHistory}
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
