import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, commandHeaders } from "../api/client";
import { Notice, Status } from "../components";

export function Documents({
  tenant,
  caseId,
  canRetry,
}: {
  tenant: string;
  caseId: string;
  canRetry: boolean;
}) {
  const cache = useQueryClient();
  const [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const documents = useQuery({
    queryKey: ["documents", tenant, caseId],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/cases/{caseId}/documents", {
          params: { path: { tenantId: tenant, caseId } },
        }),
      ),
    refetchInterval: (query) =>
      !query.state.error &&
      query.state.data?.items.some((j) =>
        ["QUEUED", "RUNNING", "RETRY_WAIT"].includes(j.status),
      )
        ? Math.min(
            30000,
            2000 * 2 ** Math.min(query.state.dataUpdateCount - 1, 4),
          )
        : false,
  });
  async function download(jobId: string) {
    setBusy(true);
    setError(undefined);
    try {
      const result = await unwrap(
        api.POST(
          "/api/v1/tenants/{tenantId}/cases/{caseId}/documents/{jobId}/download-url",
          { params: { path: { tenantId: tenant, caseId, jobId } } },
        ),
      );
      const link = document.createElement("a");
      link.href = result.url;
      link.rel = "noreferrer";
      link.click();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function retry(jobId: string, attempt: number) {
    setBusy(true);
    setError(undefined);
    try {
      await unwrap(
        api.POST("/api/v1/tenants/{tenantId}/jobs/{jobId}/retry", {
          params: {
            path: { tenantId: tenant, jobId },
            header: commandHeaders(),
          },
          body: { expectedAttempt: attempt },
        }),
      );
      await cache.invalidateQueries({
        queryKey: ["documents", tenant, caseId],
      });
      await cache.invalidateQueries({ queryKey: ["case", tenant, caseId] });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>Approved document</h2>
      <p>
        The purchase is approved. Document processing has a separate status.
      </p>
      <Notice error={error} />
      <Notice error={documents.error} />
      {documents.isPending && <p role="status">Loading document status…</p>}
      {!documents.isPending &&
        !documents.error &&
        !documents.data?.items.length && (
          <p>
            No document job is available for this purchase. Requests approved
            before template support cannot be rendered automatically.
          </p>
        )}
      {!documents.error &&
        documents.data?.items.map((job) => (
          <div className="member" key={job.jobId}>
            <div>
              <Status value={job.status} />
              <p>
                Generation attempt {job.attempt}
                {job.byteSize ? ` · ${Math.ceil(job.byteSize / 1024)} KB` : ""}
              </p>
              {job.failureCode && (
                <p role="status">
                  Generation needs attention:{" "}
                  {job.failureCode.toLowerCase().replaceAll("_", " ")}.
                </p>
              )}
            </div>
            {job.status === "SUCCEEDED" && (
              <button disabled={busy} onClick={() => void download(job.jobId)}>
                Download Word document
              </button>
            )}
            {job.status === "FAILED" && canRetry && (
              <button
                disabled={busy}
                onClick={() => void retry(job.jobId, job.attempt)}
              >
                Retry generation
              </button>
            )}
          </div>
        ))}
      <p className="hint">
        Download links expire after 60 seconds. Previously issued links remain
        usable until they expire.
      </p>
    </section>
  );
}
