import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
    agent: {
      conversations, conversationMessages, chat, deleteConversation,
      chatStream: async function* (message: string, conversationId: string | null) {
        yield { type: "status", label: "Looking up transactions" };
        yield { type: "complete", data: await chat(message, conversationId) };
      },
    },
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
    vi.useRealTimers();
    vi.unstubAllGlobals();
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
    vi.stubGlobal("PointerEvent", MouseEvent);
    let resolveReply!: (value: unknown) => void;
    chat.mockReturnValue(new Promise((resolve) => { resolveReply = resolve; }));
    const user = userEvent.setup();
    render(<MeriChatProvider><ChatSurfaces /></MeriChatProvider>);
    await screen.findByText("Ask about your actual financial plan");
    await user.type(screen.getByPlaceholderText("Ask Meri about your finances…"), "How was September?");
    await user.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Looking up transactions");
    await user.click(screen.getByRole("button", { name: "Open Meri as popup" }));
    expect(screen.getByRole("dialog", { name: "Meri chat" })).toBeInTheDocument();
    resolveReply({ conversation_id: "chat-2", reply: "September spending was $300.", tool_calls: [], structured_results: [] });
    expect(await screen.findByText("September spending was $300.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Close Meri popup" }));
    expect(screen.getByText("September spending was $300.")).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText("Ask Meri about your finances…"), "And October?");
    await user.click(screen.getByRole("button", { name: "Open Meri as popup" }));
    expect(screen.getByPlaceholderText("Ask Meri about your finances…")).toHaveValue("And October?");
    const dialog = screen.getByRole("dialog", { name: "Meri chat" });
    await user.click(screen.getByRole("button", { name: /Move Meri from right/ }));
    expect(dialog).toHaveAttribute("data-position", "center");
    await user.click(screen.getByRole("button", { name: /Move Meri from center/ }));
    expect(dialog).toHaveAttribute("data-position", "left");
    const resize = screen.getByRole("button", { name: "Resize Meri chat" });
    resize.focus();
    fireEvent.keyDown(resize, { key: "ArrowLeft" });
    expect(dialog).toHaveStyle({ width: "min(388px, calc(100vw - 2rem))" });
    const heading = screen.getByRole("heading", { name: "Meri" });
    fireEvent.pointerDown(heading, { pointerId: 1, pointerType: "mouse", clientX: 100, clientY: 100 });
    fireEvent.pointerMove(window, { pointerId: 1, clientX: 900, clientY: 120 });
    fireEvent.pointerUp(window, { pointerId: 1, clientX: 900, clientY: 120 });
    expect(dialog).toHaveAttribute("data-position", "right");
    class TouchPointerEvent extends MouseEvent {
      pointerId: number;
      pointerType: string;
      constructor(type: string, init: MouseEventInit & { pointerId?: number; pointerType?: string }) {
        super(type, init);
        this.pointerId = init.pointerId ?? 1;
        this.pointerType = init.pointerType ?? "touch";
      }
    }
    vi.stubGlobal("PointerEvent", TouchPointerEvent);
    vi.useFakeTimers();
    fireEvent.pointerDown(heading, { pointerId: 2, pointerType: "touch", clientX: 900, clientY: 100 });
    vi.advanceTimersByTime(350);
    fireEvent.pointerMove(window, { pointerId: 2, pointerType: "touch", clientX: 100, clientY: 120 });
    fireEvent.pointerUp(window, { pointerId: 2, pointerType: "touch", clientX: 100, clientY: 120 });
    expect(dialog).toHaveAttribute("data-position", "left");
  });
});
