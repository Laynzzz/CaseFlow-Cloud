import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, commandHeaders } from "../api/client";
import { auth } from "../auth";
import { Notice, Status } from "../components";

export function SourceText({
  tenant,
  sourceId,
  caseId,
}: {
  tenant: string;
  sourceId: string;
  caseId?: string;
}) {
  const result = useQuery({
    queryKey: ["source-text", tenant, sourceId, caseId],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/sources/{sourceId}/chunks", {
          params: { path: { tenantId: tenant, sourceId }, query: { caseId } },
        }),
      ),
  });
  if (result.error) return <Notice error={result.error} />;
  if (!result.data) return <p>Loading source text…</p>;
  return (
    <div>
      <p className="hint">
        Extracted from {result.data.metadata.pageCount} page(s). Adjacent
        passages may overlap. Check the original file when layout matters.
      </p>
      {result.data.items.map((chunk) => (
        <blockquote key={chunk.id}>
          <small>
            Page {chunk.page} · characters {chunk.start}–{chunk.end}
          </small>
          <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
            {chunk.text}
          </p>
        </blockquote>
      ))}
    </div>
  );
}

export function Sources({
  tenant,
  caseId,
  caseVersion,
  canUpload = false,
}: {
  tenant: string;
  caseId?: string;
  caseVersion?: number;
  canUpload?: boolean;
}) {
  const cache = useQueryClient();
  const [name, setName] = useState("");
  const [file, setFile] = useState<File>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [expanded, setExpanded] = useState<string>();
  const [uploadKey, setUploadKey] = useState(0);
  const sourceList = useQuery({
    queryKey: ["sources", tenant, caseId],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/sources", {
          params: {
            path: { tenantId: tenant },
            query: caseId ? { caseId } : {},
          },
        }),
      ),
    refetchInterval: (query) =>
      !query.state.error &&
      query.state.data?.items.some((s) => s.state === "INDEXING")
        ? Math.min(
            30000,
            2000 * 2 ** Math.min(query.state.dataUpdateCount - 1, 4),
          )
        : false,
  });
  async function refresh() {
    await cache.invalidateQueries({ queryKey: ["sources", tenant] });
    if (caseId) {
      await cache.invalidateQueries({ queryKey: ["case", tenant, caseId] });
      await cache.invalidateQueries({ queryKey: ["audit", tenant, caseId] });
    }
  }
  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    const extension = file.name.split(".").pop()?.toLowerCase();
    if (
      !["pdf", "txt"].includes(extension ?? "") ||
      file.size === 0 ||
      file.size > 10485760
    ) {
      setError("Choose a nonempty PDF or TXT file up to 10 MB.");
      return;
    }
    setBusy(true);
    setError(undefined);
    try {
      const source = await unwrap(
        api.POST("/api/v1/tenants/{tenantId}/sources", {
          params: { path: { tenantId: tenant }, header: commandHeaders() },
          body: {
            name,
            kind: caseId ? "QUOTE" : "POLICY",
            caseId,
            expectedCaseVersion: caseVersion,
            byteSize: file.size,
            mediaType: extension === "pdf" ? "application/pdf" : "text/plain",
          },
        }),
      );
      await auth.updateToken(30);
      const response = await fetch(
        `/api/v1/tenants/${tenant}/sources/${source.id}/content`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${auth.token}`,
            "Content-Type": "application/octet-stream",
          },
          body: file,
        },
      );
      if (!response.ok)
        throw new Error(
          "Upload failed. Check access and reload the request before trying again.",
        );
      await unwrap(
        api.POST("/api/v1/tenants/{tenantId}/sources/{sourceId}/finalize", {
          params: {
            path: { tenantId: tenant, sourceId: source.id },
            header: commandHeaders(),
          },
          body: {
            expectedVersion: source.version,
            expectedCaseVersion: caseVersion,
          },
        }),
      );
      setFile(undefined);
      setName("");
      setUploadKey((k) => k + 1);
    } catch (e) {
      setError(e);
    } finally {
      await refresh();
      setBusy(false);
    }
  }
  async function changeState(
    sourceId: string,
    version: number,
    action: "publish" | "deactivate",
  ) {
    setBusy(true);
    setError(undefined);
    try {
      const options = {
        params: {
          path: { tenantId: tenant, sourceId },
          header: commandHeaders(),
        },
        body: { expectedVersion: version },
      };
      await unwrap(
        action === "publish"
          ? api.POST(
              "/api/v1/tenants/{tenantId}/sources/{sourceId}/publish",
              options,
            )
          : api.POST(
              "/api/v1/tenants/{tenantId}/sources/{sourceId}/deactivate",
              options,
            ),
      );
      await refresh();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>{caseId ? "Vendor quotes" : "Purchasing policies"}</h2>
      <p>
        {caseId
          ? "Attach the quote that supports this purchase. Your saved purchase details stay under your control."
          : "Upload a policy, inspect its extracted text, then publish it for purchase reviews."}
      </p>
      <Notice error={error} />
      <Notice error={sourceList.error} />
      {canUpload && (
        <form onSubmit={upload}>
          <label>
            {caseId ? "Quote name" : "Policy name"}
            <input
              required
              maxLength={120}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            PDF or TXT file
            <input
              key={uploadKey}
              type="file"
              accept=".pdf,.txt"
              onChange={(e) => setFile(e.target.files?.[0])}
            />
          </label>
          <p className="hint">
            Up to 10 MB and 50 pages. PDFs must contain selectable text; scanned
            images and encrypted files are unsupported.
          </p>
          <button disabled={busy || !file}>
            {busy ? "Uploading…" : "Upload and index"}
          </button>
        </form>
      )}
      <button
        className="text-button"
        disabled={busy}
        onClick={() => void refresh()}
      >
        Check source status
      </button>
      {!sourceList.error && sourceList.data?.items.length === 0 && (
        <p>No {caseId ? "quotes attached" : "policies uploaded"} yet.</p>
      )}
      {!sourceList.error &&
        sourceList.data?.items.map((source) => (
          <div key={source.id}>
            <div className="member">
              <div>
                <strong>{source.name}</strong>
                <p>
                  {Math.ceil(source.byteSize / 1024)} KB · version{" "}
                  {source.version}
                </p>
              </div>
              <Status value={source.state} />
              {source.state === "FAILED" && (
                <p role="status">
                  Could not read this file:{" "}
                  {source.failureCode?.toLowerCase().replaceAll("_", " ")}.
                  Upload a corrected file; manual entry remains available.
                </p>
              )}
              {["INDEXED", "PUBLISHED", "DEACTIVATED"].includes(
                source.state,
              ) && (
                <button
                  className="secondary"
                  onClick={() =>
                    setExpanded(expanded === source.id ? undefined : source.id)
                  }
                >
                  {expanded === source.id ? "Hide text" : "View source text"}
                </button>
              )}
              {!caseId && canUpload && source.state === "INDEXED" && (
                <button
                  disabled={busy}
                  onClick={() =>
                    void changeState(source.id, source.version, "publish")
                  }
                >
                  Publish policy
                </button>
              )}
              {!caseId && canUpload && source.state === "PUBLISHED" && (
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() =>
                    void changeState(source.id, source.version, "deactivate")
                  }
                >
                  Deactivate policy
                </button>
              )}
            </div>
            {expanded === source.id && (
              <SourceText tenant={tenant} sourceId={source.id} />
            )}
          </div>
        ))}
    </section>
  );
}
