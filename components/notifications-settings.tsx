import { Panel, PanelHeader } from "@/components/panel";

const notificationOptions = [
  { label: "Weekly portfolio digest", hint: "Every Monday at 8:00 AM" },
  { label: "Allocation drift alerts", hint: "When drift exceeds 5%" },
  { label: "Large transaction alerts", hint: "Transactions over $2,500" },
  { label: "New AI recommendations", hint: "When analysis surfaces opportunities" },
  { label: "Bill & contribution reminders", hint: "Two days before due dates" },
] as const;

export function NotificationsSettings() {
  return (
    <Panel>
      <PanelHeader
        title="Notifications"
        description="Notification delivery is coming soon"
      />
      <div className="divide-y divide-border px-4">
        {notificationOptions.map((option) => (
          <div
            key={option.label}
            className="grid grid-cols-1 gap-2 py-3.5 sm:grid-cols-[220px_1fr] sm:items-center sm:gap-4"
          >
            <div>
              <p className="text-[13px] font-medium text-foreground">{option.label}</p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                {option.hint} · Coming soon
              </p>
            </div>
            <div className="flex sm:justify-start">
              <button
                type="button"
                role="switch"
                aria-label={option.label}
                aria-checked={false}
                disabled
                className="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full bg-muted transition-colors disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span className="inline-block size-4 translate-x-0.5 rounded-full bg-background shadow-sm" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}
