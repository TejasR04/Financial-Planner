"use client";

import { useEffect, useMemo, useState } from "react";
import { Copy, KeyRound, Plus, Trash2 } from "lucide-react";
import { Panel, PanelHeader } from "@/components/panel";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth-context";
import { api, ApiAgentToken, ApiAgentTokenCreated, ApiError, getMcpEndpoint } from "@/lib/api-client";

const inputClass = "h-8 w-full rounded-md border border-border bg-background px-2.5 text-[13px] text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-ring focus:ring-3 focus:ring-ring/20 disabled:cursor-not-allowed disabled:opacity-60";

function makeHermesConfig(endpoint: string) {
  return `timezone: America/New_York

mcp_servers:
  meridian:
    url: "${endpoint}"
    headers:
      Authorization: "Bearer \${MERIDIAN_AGENT_TOKEN}"
    connect_timeout: 60
    timeout: 60
    tools:
      include:
        - get_current_financial_summary
        - get_daily_report
        - list_daily_reports
        - get_report_changes
      resources: false
      prompts: false`;
}

function formatDate(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function IntegrationsSettings() {
  const { isDemo } = useAuth();
  const endpoint = useMemo(() => getMcpEndpoint(), []);
  const config = useMemo(() => makeHermesConfig(endpoint), [endpoint]);
  const [tokens, setTokens] = useState<ApiAgentToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [tokenName, setTokenName] = useState("Hermes daily report");
  const [creating, setCreating] = useState(false);
  const [createdToken, setCreatedToken] = useState<ApiAgentTokenCreated | null>(null);
  const [confirmingRevoke, setConfirmingRevoke] = useState<string | null>(null);
  const [workingTokenId, setWorkingTokenId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (isDemo) {
      setTokens([]);
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setError(null);
    api.integrations.tokens()
      .then((result) => { if (active) setTokens(result.data); })
      .catch((cause) => {
        if (active) setError(cause instanceof ApiError ? cause.message : "Couldn't load agent tokens.");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [isDemo]);

  async function reloadTokens() {
    const result = await api.integrations.tokens();
    setTokens(result.data);
  }

  async function createToken(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isDemo || !tokenName.trim()) return;
    setCreating(true);
    setError(null);
    setFeedback(null);
    try {
      const result = await api.integrations.createToken(tokenName.trim());
      setCreatedToken(result);
      setTokenName("");
      try {
        await reloadTokens();
      } catch {
        setError("Token created, but the token list could not be refreshed.");
      }
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Couldn't create an agent token.");
    } finally {
      setCreating(false);
    }
  }

  async function revokeToken(token: ApiAgentToken) {
    setWorkingTokenId(token.id);
    setError(null);
    setFeedback(null);
    try {
      await api.integrations.revokeToken(token.id);
      setConfirmingRevoke(null);
      setFeedback(`${token.name} was revoked.`);
      setTokens((rows) => rows.map((row) => row.id === token.id ? { ...row, revoked_at: new Date().toISOString() } : row));
      try {
        await reloadTokens();
      } catch {
        setError("Token revoked, but the token list could not be refreshed.");
      }
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Couldn't revoke that token.");
    } finally {
      setWorkingTokenId(null);
    }
  }

  async function copy(value: string, label: string) {
    setError(null);
    try {
      await navigator.clipboard.writeText(value);
      setFeedback(`${label} copied.`);
    } catch {
      setError("Clipboard access is unavailable. Select and copy the text instead.");
    }
  }

  return (
    <div className="space-y-4">
      <Panel>
        <PanelHeader
          title="Agent access"
          description="Connect Hermes to read your financial reports through Meridian’s MCP endpoint."
        />
        {isDemo ? (
          <p className="border-b border-border bg-muted/30 px-4 py-3 text-[12px] text-muted-foreground">
            Agent tokens are unavailable in demo mode. Sign in to create a real read-only credential.
          </p>
        ) : null}
        {error ? <p role="alert" className="border-b border-destructive/30 bg-destructive/5 px-4 py-3 text-[12px] text-destructive">{error}</p> : null}
        {feedback ? <p role="status" className="border-b border-positive/30 bg-positive/5 px-4 py-3 text-[12px] text-positive">{feedback}</p> : null}

        {createdToken ? (
          <div className="space-y-2 border-b border-border bg-primary/5 px-4 py-3">
            <div className="flex items-center gap-2 text-[13px] font-medium text-foreground">
              <KeyRound className="size-4" />
              Copy this token now. Meridian will not show it again.
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <code className="min-w-0 flex-1 break-all rounded-md border border-border bg-background px-3 py-2 font-mono text-[12px]">{createdToken.token}</code>
              <Button variant="outline" size="sm" onClick={() => void copy(createdToken.token, "Token")}>
                <Copy /> Copy token
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setCreatedToken(null)}>Hide token</Button>
            </div>
            <p className="text-[11px] text-muted-foreground">Scope: {createdToken.scope} · Expires {formatDate(createdToken.expires_at)}. Put the secret in <code>~/.hermes/.env</code>, never in the YAML configuration.</p>
          </div>
        ) : null}

        <div className="space-y-4 px-4 py-4">
          <div>
            <p className="text-[12px] font-medium text-foreground">MCP endpoint</p>
            <code className="mt-1 block break-all rounded-md border border-border bg-muted/30 px-3 py-2 font-mono text-[12px] text-muted-foreground">{endpoint}</code>
          </div>

          <form onSubmit={(event) => void createToken(event)} className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <div className="min-w-0 flex-1">
              <label htmlFor="agent-token-name" className="mb-1 block text-[12px] font-medium text-foreground">Token name</label>
              <input
                id="agent-token-name"
                className={inputClass}
                value={tokenName}
                onChange={(event) => setTokenName(event.target.value)}
                maxLength={80}
                autoComplete="off"
                disabled={isDemo || creating}
              />
            </div>
            <Button type="submit" size="sm" disabled={isDemo || creating || !tokenName.trim()}>
              <Plus /> {creating ? "Creating…" : "Create token"}
            </Button>
          </form>

          <div>
            <div className="mb-1 flex items-center justify-between gap-2">
              <p className="text-[12px] font-medium text-foreground">Hermes MCP configuration</p>
              <Button variant="outline" size="xs" onClick={() => void copy(config, "Hermes configuration")}>
                <Copy /> Copy config
              </Button>
            </div>
            <pre className="overflow-x-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-[11px] leading-5 text-muted-foreground"><code>{config}</code></pre>
            <p className="mt-1 text-[11px] text-muted-foreground">The configuration references <code>MERIDIAN_AGENT_TOKEN</code>; it does not contain your credential.</p>
          </div>
        </div>
      </Panel>

      <Panel>
        <PanelHeader title="Agent tokens" description="Tokens can read reports and can be revoked at any time." />
        {loading ? (
          <p className="px-4 py-6 text-center text-[12px] text-muted-foreground">Loading tokens…</p>
        ) : tokens.length === 0 ? (
          <div className="px-4 py-6 text-center">
            <p className="text-[12px] text-muted-foreground">No agent tokens yet.</p>
            <p className="mt-1 text-[11px] text-muted-foreground">Create one above to connect Hermes.</p>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {tokens.map((token) => {
              const revoked = token.revoked_at !== null;
              return (
                <li key={token.id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate text-[13px] font-medium text-foreground">{token.name}</p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground"><code>{token.prefix}••••••</code> · {token.scope} · Expires {formatDate(token.expires_at)}</p>
                    {revoked ? <p className="mt-0.5 text-[11px] text-muted-foreground">Revoked {formatDate(token.revoked_at!)}</p> : null}
                  </div>
                  {revoked ? (
                    <span className="text-[11px] font-medium text-muted-foreground">Revoked</span>
                  ) : confirmingRevoke === token.id ? (
                    <div className="flex items-center gap-2">
                      <span className="text-[11px] text-muted-foreground">Revoke this token?</span>
                      <Button variant="destructive" size="xs" onClick={() => void revokeToken(token)} disabled={workingTokenId !== null}>
                        <Trash2 /> {workingTokenId === token.id ? "Revoking…" : "Confirm"}
                      </Button>
                      <Button variant="ghost" size="xs" onClick={() => setConfirmingRevoke(null)} disabled={workingTokenId !== null}>Cancel</Button>
                    </div>
                  ) : (
                    <Button variant="outline" size="xs" onClick={() => setConfirmingRevoke(token.id)} disabled={workingTokenId !== null}>
                      <Trash2 /> Revoke
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Panel>
    </div>
  );
}

export { makeHermesConfig };
