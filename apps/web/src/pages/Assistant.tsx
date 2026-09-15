import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, commandHeaders } from "../api/client";
import type { components } from "../api/schema";
import { Notice, Status } from "../components";

type Schemas = components["schemas"];
type Field = "vendor" | "currency" | "lineItems";
const fields: Field[] = ["vendor", "currency", "lineItems"];
const show = (value: unknown) => {
  if (value === null || value === undefined) return "Not supplied";
  if (typeof value === "string") return value || "Not entered";
  if (Array.isArray(value)) {
    return value.length
      ? value
          .map(
            (item) =>
              `${item.description}: ${item.quantity} × ${item.unitPrice} each`,
          )
          .join("\n")
      : "No line items";
  }
  return String(value);
};

function Citations({
  citations,
  evidence,
}: {
  citations: Schemas["AICitation"][];
  evidence: Schemas["AIResult"]["evidence"];
}) {
  return (
    <>
      {citations.map((cite, index) => {
        const source = evidence[cite.chunkId];
        return (
          <blockquote key={index}>
            <small>
              Source {source?.sourceId.slice(0, 8)} · page {source?.page}
            </small>
            <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
              {cite.quote}
            </p>
          </blockquote>
        );
      })}
    </>
  );
}

export function Assistant({
  tenant,
  item,
  editable,
  canReview,
}: {
  tenant: string;
  item: Schemas["Case"];
  editable: boolean;
  canReview: boolean;
}) {
  const cache = useQueryClient(),
    path = { tenantId: tenant, caseId: item.id };
  const [sourceId, setSourceId] = useState("");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const [selected, setSelected] = useState<Record<string, Field[]>>({});
  const results = useQuery({
    queryKey: ["assistant", tenant, item.id, item.version],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/cases/{caseId}/assistant", {
          params: { path },
        }),
      ),
    refetchInterval: (q) =>
      !q.state.error &&
      q.state.data?.items.some((j) =>
        ["QUEUED", "RUNNING", "RETRY_WAIT"].includes(j.status),
      )
        ? Math.min(30000, 2000 * 2 ** Math.min(q.state.dataUpdateCount - 1, 4))
        : false,
  });
  const sources = useQuery({
    queryKey: ["sources", tenant, item.id],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/sources", {
          params: { path: { tenantId: tenant }, query: { caseId: item.id } },
        }),
      ),
  });
  async function run(kind: "EXTRACTION" | "REVIEW") {
    setBusy(true);
    setError(undefined);
    try {
      await unwrap(
        api.POST("/api/v1/tenants/{tenantId}/cases/{caseId}/assistant", {
          params: { path, header: commandHeaders() },
          body: {
            kind,
            expectedVersion: item.version,
            ...(kind === "EXTRACTION" ? { sourceId } : {}),
          },
        }),
      );
      await cache.invalidateQueries({
        queryKey: ["assistant", tenant, item.id],
      });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function accept(job: Schemas["AIJob"]) {
    setBusy(true);
    setError(undefined);
    try {
      await unwrap(
        api.POST(
          "/api/v1/tenants/{tenantId}/cases/{caseId}/assistant/{jobId}/accept",
          {
            params: {
              path: { ...path, jobId: job.jobId },
              header: commandHeaders(),
            },
            body: {
              expectedVersion: item.version,
              fields: selected[job.jobId] ?? [],
            },
          },
        ),
      );
      setSelected({});
      await cache.invalidateQueries({ queryKey: ["case", tenant, item.id] });
      await cache.invalidateQueries({
        queryKey: ["assistant", tenant, item.id],
      });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>AI review assistant</h2>
      <p>
        Experimental assistance. Check each suggestion against its source. You
        choose what to save; people make every approval decision.
      </p>
      <Notice error={error} />
      <Notice error={results.error} />
      {results.data && !results.data.enabled && (
        <p role="status">
          Live AI testing is not configured. You can enter purchase details
          manually and read or search the policies above.
        </p>
      )}
      {editable && (
        <>
          <label>
            Quote to extract
            <select
              value={sourceId}
              onChange={(e) => setSourceId(e.target.value)}
            >
              <option value="">Select an indexed quote</option>
              {sources.data?.items
                .filter((s) => s.state === "INDEXED")
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
            </select>
          </label>
          <button
            disabled={busy || !results.data?.enabled || !sourceId}
            onClick={() => void run("EXTRACTION")}
          >
            Suggest purchase details
          </button>
        </>
      )}
      {canReview && (
        <button
          className="secondary"
          disabled={busy || !results.data?.enabled}
          onClick={() => void run("REVIEW")}
        >
          Create policy review
        </button>
      )}
      <button
        className="text-button"
        onClick={() =>
          void cache.invalidateQueries({
            queryKey: ["assistant", tenant, item.id],
          })
        }
      >
        Check AI status
      </button>
      {!results.error &&
        results.data?.items.map((job) => (
          <article key={job.jobId}>
            <h3>
              {job.kind === "EXTRACTION"
                ? "Purchase suggestions"
                : "Policy review"}{" "}
              · purchase version {job.revision}
            </h3>
            <Status value={job.status} />
            {job.stale && (
              <p role="status">
                This result uses an older purchase or policy selection. It
                cannot be accepted into the current draft.
              </p>
            )}
            {job.status === "FAILED" && (
              <p>
                Assistance unavailable:{" "}
                {job.failureCode?.toLowerCase().replaceAll("_", " ")}. Continue
                manually or request a new check after correcting the issue.
              </p>
            )}
            {job.result && job.kind === "EXTRACTION" && (
              <>
                {fields.map((field) => {
                  const proposal = (
                    job.result!.output as Schemas["AIExtraction"]
                  )[field];
                  return (
                    <div key={field}>
                      <label>
                        <input
                          type="checkbox"
                          disabled={
                            !editable ||
                            job.stale ||
                            proposal.value === null ||
                            busy
                          }
                          checked={(selected[job.jobId] ?? []).includes(field)}
                          onChange={(e) =>
                            setSelected((previous) => ({
                              ...previous,
                              [job.jobId]: e.target.checked
                                ? [...(previous[job.jobId] ?? []), field]
                                : (previous[job.jobId] ?? []).filter(
                                    (f) => f !== field,
                                  ),
                            }))
                          }
                        />
                        {field === "lineItems"
                          ? "Line items"
                          : field === "vendor"
                            ? "Vendor"
                            : "Currency"}
                      </label>
                      <div className="member">
                        <div>
                          <small>Currently saved</small>
                          <pre style={{ whiteSpace: "pre-wrap" }}>
                            {show(item.purchase[field])}
                          </pre>
                        </div>
                        <div>
                          <small>Suggested</small>
                          <pre style={{ whiteSpace: "pre-wrap" }}>
                            {show(proposal.value)}
                          </pre>
                        </div>
                      </div>
                      <Citations
                        citations={proposal.citations}
                        evidence={job.result!.evidence}
                      />
                    </div>
                  );
                })}
                <p>
                  Quoted total:{" "}
                  {show(
                    (job.result.output as Schemas["AIExtraction"]).total.value,
                  )}
                  . The saved total is calculated from accepted line items and
                  currency.
                </p>
                {(job.result.output as Schemas["AIExtraction"]).warnings.map(
                  (warning, i) => (
                    <p key={i}>{warning}</p>
                  ),
                )}
                {editable && (
                  <button
                    disabled={busy || job.stale || !selected[job.jobId]?.length}
                    onClick={() => void accept(job)}
                  >
                    Accept selected fields
                  </button>
                )}
              </>
            )}
            {job.result && job.kind === "REVIEW" && (
              <>
                <p>{(job.result.output as Schemas["AIReview"]).summary}</p>
                {(job.result.output as Schemas["AIReview"])
                  .insufficient_evidence && (
                  <p>
                    There is not enough policy evidence for a complete review.
                  </p>
                )}
                {(
                  job.result.output as Schemas["AIReview"]
                ).missing_information.map((missing, i) => (
                  <p key={i}>Missing information: {missing}</p>
                ))}
                {(job.result.output as Schemas["AIReview"]).policy_findings.map(
                  (finding, i) => (
                    <div key={i}>
                      <p>{finding.claim}</p>
                      <Citations
                        citations={finding.citations}
                        evidence={job.result!.evidence}
                      />
                    </div>
                  ),
                )}
              </>
            )}
          </article>
        ))}
    </section>
  );
}
