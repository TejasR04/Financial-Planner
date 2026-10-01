import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { GeminiAssistant } from "@/components/gemini-assistant";
import { MeriChatProvider, useMeriChat } from "@/components/meri-chat-context";
import { MeriChatDock } from "@/components/meri-chat-dock";

const { conversations, conversationMessages, chat, deleteConversation } = vi.hoisted(() => ({
  conversations: vi.fn(),
  conversationMessages: vi.fn(),
  chat: vi.fn(),
  deleteConversation: vi.fn(),
}));

vi.mock("@/lib/api-client", () => ({
  ApiError: class ApiError extends Error {},
  api: {
    agent: { conversations, conversationMessages, chat, deleteConversation },
  },
}));
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ isDemo: false }) }));

function ChatSurfaces() {
  const { popupOpen } = useMeriChat();
  return <>{!popupOpen && <GeminiAssistant />}<MeriChatDock /></>;
}

describe("GeminiAssistant chat history", () => {
  beforeEach(() => {
    conversations.mockReset().mockResolvedValue([
      {
        id: "chat-1",
        title: "Compare dining spending",
        created_at: "2026-09-19T12:00:00Z",
        updated_at: "2026-09-19T12:05:00Z",
        message_count: 2,
      },
    ]);
    conversationMessages.mockReset().mockResolvedValue([
      {
        id: "message-1",
        role: "user",
        content: "Compare dining spending",
        created_at: "2026-09-19T12:00:00Z",
      },
      {
        id: "message-2",
        role: "assistant",
        content: "Here is the comparison.",
        created_at: "2026-09-19T12:05:00Z",
      },
    ]);
    chat.mockReset();
    deleteConversation.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("starts blank after mounting and opens a saved chat only from history", async () => {
    const user = userEvent.setup();
    render(<MeriChatProvider><GeminiAssistant /></MeriChatProvider>);

    expect(await screen.findByText("Ask about your actual financial plan")).toBeInTheDocument();
    expect(screen.queryByText("Here is the comparison.")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "History (1)" }));
    await user.click(screen.getByText("Compare dining spending").closest("button")!);

    expect(await screen.findByText("Here is the comparison.")).toBeInTheDocument();
    expect(conversationMessages).toHaveBeenCalledWith("chat-1");

    await user.click(screen.getByRole("button", { name: "New chat" }));
    expect(screen.getByText("Ask about your actual financial plan")).toBeInTheDocument();
    expect(screen.queryByText("Here is the comparison.")).not.toBeInTheDocument();
  });

  it("starts a new saved chat when an opened chat has been inactive", async () => {
    let now = 1_000;
    vi.spyOn(Date, "now").mockImplementation(() => now);
    chat.mockResolvedValue({
      conversation_id: "chat-2",
      reply: "A fresh response.",
      tool_calls: [],
      structured_results: [],
    });
    const user = userEvent.setup();
    render(<MeriChatProvider><GeminiAssistant /></MeriChatProvider>);

    await screen.findByText("Ask about your actual financial plan");
    await user.click(screen.getByRole("button", { name: "History (1)" }));
    await user.click(screen.getByText("Compare dining spending").closest("button")!);
    await screen.findByText("Here is the comparison.");

    now += 31 * 60 * 1000;
    await user.type(screen.getByPlaceholderText("Ask Meri about your finances…"), "New topic");
    await user.click(screen.getByRole("button", { name: "Send message" }));

    expect(await screen.findByText("A fresh response.")).toBeInTheDocument();
    expect(chat).toHaveBeenCalledWith("New topic", null);
    expect(screen.queryByText("Here is the comparison.")).not.toBeInTheDocument();
  });

  it("shares an active reply and draft with the popup", async () => {
    let resolveReply!: (value: unknown) => void;
    chat.mockReturnValue(new Promise((resolve) => { resolveReply = resolve; }));
    const user = userEvent.setup();
    render(<MeriChatProvider><ChatSurfaces /></MeriChatProvider>);
    await screen.findByText("Ask about your actual financial plan");
    await user.type(screen.getByPlaceholderText("Ask Meri about your finances…"), "How was September?");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    await user.click(screen.getByRole("button", { name: "Open Meri as popup" }));
    expect(screen.getByRole("dialog", { name: "Meri chat" })).toBeInTheDocument();
    resolveReply({ conversation_id: "chat-2", reply: "September spending was $300.", tool_calls: [], structured_results: [] });
    expect(await screen.findByText("September spending was $300.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close Meri popup" }));
    expect(screen.getByText("September spending was $300.")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("Ask Meri about your finances…"), "And October?");
    await user.click(screen.getByRole("button", { name: "Open Meri as popup" }));
    expect(screen.getByPlaceholderText("Ask Meri about your finances…")).toHaveValue("And October?");
  });
});
