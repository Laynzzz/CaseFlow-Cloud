import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, commandHeaders } from "../api/client";
import { Notice, Status } from "../components";
import { SourceText } from "./Sources";

export function Policies({
  tenant,
  caseId,
  version,
  editable,
}: {
  tenant: string;
  caseId: string;
  version: number;
  editable: boolean;
}) {
  const cache = useQueryClient();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const [expanded, setExpanded] = useState<string>();
  const [text, setText] = useState(""),
    [query, setQuery] = useState("");
  const path = { tenantId: tenant, caseId };
  const policies = useQuery({
    queryKey: ["policies", tenant, caseId, version],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/cases/{caseId}/policies", {
          params: { path },
        }),
      ),
  });
  const search = useQuery({
    queryKey: ["policy-search", tenant, caseId, version, query],
    enabled: !!query,
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/cases/{caseId}/policies/search", {
          params: { path, query: { query } },
        }),
      ),
  });
  async function refresh() {
    setBusy(true);
    setError(undefined);
    try {
      await unwrap(
        api.POST("/api/v1/tenants/{tenantId}/cases/{caseId}/policies/refresh", {
          params: { path, header: commandHeaders() },
          body: { expectedVersion: version },
        }),
      );
      setExpanded(undefined);
      setQuery("");
      await cache.invalidateQueries({ queryKey: ["case", tenant, caseId] });
      await cache.invalidateQueries({ queryKey: ["policies", tenant, caseId] });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>Policies for this purchase</h2>
      <p>
        {editable
          ? "Choose the currently published policies for this draft. Refreshing replaces the selection and makes older review results stale."
          : "These policy versions stay fixed for this purchase, even if an administrator later deactivates them."}
      </p>
      <Notice error={error} />
      <Notice error={policies.error} />
      {editable && (
        <button disabled={busy} onClick={() => void refresh()}>
          {busy ? "Refreshing…" : "Refresh published policies"}
        </button>
      )}
      {!policies.error && policies.data && (
        <>
          {!policies.data.initialized && (
            <p>
              Policies have not been selected yet. Starting the purchase also
              selects the published policies.
            </p>
          )}
          {policies.data.initialized && !policies.data.items.length && (
            <p>No policies were published when this selection was made.</p>
          )}
          {policies.data.items.map((policy) => (
            <div key={policy.id}>
              <div className="member">
                <div>
                  <strong>{policy.name}</strong>
                  <p>Pinned version {policy.version}</p>
                </div>
                <Status value={policy.state} />
                <button
                  className="secondary"
                  onClick={() =>
                    setExpanded(expanded === policy.id ? undefined : policy.id)
                  }
                >
                  {expanded === policy.id ? "Hide policy" : "Read policy"}
                </button>
              </div>
              {expanded === policy.id && (
                <SourceText
                  tenant={tenant}
                  caseId={caseId}
                  sourceId={policy.id}
                />
              )}
            </div>
          ))}
          {!!policies.data.items.length && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setQuery(text.trim());
              }}
            >
              <label>
                Search policy text
                <input
                  required
                  maxLength={500}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  placeholder="Example: cost center"
                />
              </label>
              <button>Find passages</button>
              <p className="hint">
                Keyword search returns up to five matching passages. This is
                source text, not an AI interpretation.
              </p>
            </form>
          )}
        </>
      )}
      <Notice error={search.error} />
      {!search.error && search.data && (
        <div>
          {!search.data.items.length && (
            <p>
              No matching passage. Try different words or read the policy
              directly.
            </p>
          )}
          {search.data.items.map((chunk) => (
            <blockquote key={chunk.id}>
              <strong>
                {chunk.name} · page {chunk.page}
              </strong>
              <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
                {chunk.text}
              </p>
            </blockquote>
          ))}
        </div>
      )}
    </section>
  );
}
