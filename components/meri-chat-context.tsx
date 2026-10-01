"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api, ApiError, type ApiAgentChatResponse, type ApiAgentConversation } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools?: ApiAgentChatResponse["tool_calls"];
};

const CHAT_INACTIVITY_MS = 30 * 60 * 1000;
const MeriChatContext = createContext<ReturnType<typeof useMeriChatState> | null>(null);

function temporaryId(role: ChatMessage["role"]) {
  return `${role}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function useMeriChatState() {
  const { isDemo } = useAuth();
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
  const [popupOpen, setPopupOpen] = useState(false);
  const lastActivityRef = useRef<number | null>(null);
  const sendingRef = useRef(false);

  useEffect(() => {
    if (isDemo) { setLoadingHistory(false); return; }
    let cancelled = false;
    api.agent.conversations()
      .then((history) => { if (!cancelled) setConversations(history); })
      .catch((cause) => { if (!cancelled) setError(cause instanceof Error ? cause.message : "Could not load chat history."); })
      .finally(() => { if (!cancelled) setLoadingHistory(false); });
    return () => { cancelled = true; };
  }, [isDemo]);

  async function refreshConversations() {
    setConversations(await api.agent.conversations());
  }

  async function openConversation(conversationId: string) {
    if (sendingRef.current || loadingConversation) return;
    setLoadingConversation(true);
    setError(null);
    try {
      const history = await api.agent.conversationMessages(conversationId);
      setMessages(history.map((message) => ({ id: message.id, role: message.role, content: message.content })));
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
    if (sendingRef.current) return;
    setMessages([]);
    setActiveConversationId(null);
    lastActivityRef.current = null;
    setInput("");
    setError(null);
    setConfirmClear(false);
    setShowHistory(false);
  }

  async function sendMessage(message: string) {
    const trimmed = message.trim();
    if (!trimmed || sendingRef.current) return;
    sendingRef.current = true;
    const userMessage: ChatMessage = { id: temporaryId("user"), role: "user", content: trimmed };
    const timedOut = Boolean(activeConversationId && lastActivityRef.current &&
      Date.now() - lastActivityRef.current >= CHAT_INACTIVITY_MS);
    const conversationId = timedOut ? null : activeConversationId;
    if (timedOut) {
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
      setMessages((current) => [...current, {
        id: temporaryId("assistant"), role: "assistant", content: result.reply || "Meri returned an empty response.",
        tools: result.tool_calls,
      }]);
      void refreshConversations().catch(() => setError("The response was saved, but chat history could not refresh."));
    } catch (cause) {
      setMessages((current) => current.filter((item) => item.id !== userMessage.id));
      setInput(trimmed);
      setError(cause instanceof ApiError ? cause.message : "Meri could not complete the analysis. Please try again.");
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  }

  async function clearConversation() {
    if (!activeConversationId) { startNewChat(); return; }
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

  return { messages, conversations, activeConversationId, input, setInput, loadingHistory,
    loadingConversation, sending, error, confirmClear, setConfirmClear, showHistory, setShowHistory,
    popupOpen, setPopupOpen, openConversation, startNewChat, sendMessage, clearConversation,
    deleteConversation };
}

export function MeriChatProvider({ children }: { children: ReactNode }) {
  const value = useMeriChatState();
  return <MeriChatContext.Provider value={value}>{children}</MeriChatContext.Provider>;
}

export function useMeriChat() {
  const value = useContext(MeriChatContext);
  if (!value) throw new Error("MeriChatProvider is required");
  return value;
}
