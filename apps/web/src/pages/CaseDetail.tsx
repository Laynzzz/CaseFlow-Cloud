import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, unwrap, commandHeaders } from "../api/client";
import { DraftForm } from "./DraftForm";
import { Documents } from "./Documents";
import { Sources } from "./Sources";
import { Empty, Notice, Status } from "../components";
export function CaseDetail({
  tenant,
  userId,
  roles,
}: {
  tenant: string;
  userId: string;
  roles: string[];
}) {
  const { caseId = "" } = useParams();
  const cache = useQueryClient();
  const [editing, setEditing] = useState(false),
    [correcting, setCorrecting] = useState(false);
  const [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false),
    [comment, setComment] = useState("");
  const [selected, setSelected] = useState<Record<number, string>>({});
  const [auditCursor, setAuditCursor] = useState<string>();
  const resource = { tenantId: tenant, caseId };
  const detail = useQuery({
    queryKey: ["case", tenant, caseId],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/cases/{caseId}", {
          params: { path: resource },
        }),
      ),
    refetchInterval: (query) =>
      !query.state.error &&
      query.state.data?.documentStatus &&
      ["QUEUED", "RUNNING", "RETRY_WAIT"].includes(
        query.state.data.documentStatus,
      )
        ? Math.min(
            30000,
            2000 * 2 ** Math.min(query.state.dataUpdateCount - 1, 4),
          )
        : false,
  });
  const members = useQuery({
    queryKey: ["members", tenant],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/memberships", {
          params: { path: { tenantId: tenant } },
        }),
      ),
  });
  const history = useQuery({
    queryKey: ["audit", tenant, caseId, auditCursor],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/cases/{caseId}/audit", {
          params: { path: resource, query: { cursor: auditCursor, limit: 15 } },
        }),
      ),
    enabled: !!detail.data,
  });
  const item = detail.data;
  async function perform(work: () => Promise<unknown>) {
    setBusy(true);
    setError(undefined);
    try {
      await work();
      await cache.invalidateQueries({ queryKey: ["case", tenant, caseId] });
      await cache.invalidateQueries({ queryKey: ["cases", tenant] });
      await cache.invalidateQueries({ queryKey: ["audit", tenant, caseId] });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  if (detail.isPending) return <Empty>Loading purchase…</Empty>;
  if (!item || detail.error)
    return (
      <>
        <Link to="/">Back to requests</Link>
        <Notice error={detail.error} />
      </>
    );
  const owner = item.ownerId === userId,
    admin = roles.includes("ADMIN");
  const next = item.assignments.find((a) => a.outcome === null);
  const canDecide =
    item.state === "ACTIVE" &&
    next?.userId === userId &&
    roles.includes("APPROVER") &&
    !owner;
  const canAssign =
    (owner && roles.includes("REQUESTER") && item.state === "DRAFT") ||
    (admin && ["DRAFT", "ACTIVE"].includes(item.state));
  const action = (value: "APPROVE" | "REJECT" | "CANCEL" | "COMMENT") =>
    perform(async () => {
      await unwrap(
        api.POST("/api/v1/tenants/{tenantId}/cases/{caseId}/actions", {
          params: { path: resource, header: commandHeaders() },
          body: { expectedVersion: item.version, action: value, comment },
        }),
      );
      setComment("");
    });
  return (
    <>
      <Link className="back-link" to="/">
        ← Purchase requests
      </Link>
      <div className="page-title">
        <div>
          <p className="eyebrow">{item.purchase.vendor || "Draft purchase"}</p>
          <h1>{item.purchase.description || "Untitled purchase"}</h1>
        </div>
        <Status value={item.state} />
      </div>
      <Notice error={error} />
      <Notice error={detail.error} />
      {editing || correcting ? (
        <>
          <h2>{correcting ? "Create a corrected request" : "Edit draft"}</h2>
          <DraftForm
            tenant={tenant}
            existing={item}
            originalCaseId={correcting ? item.id : undefined}
            onSaved={
              correcting
                ? undefined
                : async () => {
                    setEditing(false);
                    await cache.invalidateQueries({
                      queryKey: ["case", tenant, caseId],
                    });
                  }
            }
          />
          <button
            className="secondary"
            onClick={() => {
              setEditing(false);
              setCorrecting(false);
            }}
          >
            Close editor
          </button>
        </>
      ) : (
        <>
          <div className="detail-grid">
            <section className="panel">
              <h2>Purchase details</h2>
              <dl>
                <dt>Total</dt>
                <dd className="amount">
                  {item.purchase.currency} {item.purchase.total}
                </dd>
                <dt>Cost center</dt>
                <dd>{item.purchase.costCenter || "Not entered"}</dd>
                <dt>Business justification</dt>
                <dd>{item.purchase.justification || "Not entered"}</dd>
              </dl>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Item</th>
                      <th>Quantity</th>
                      <th>Unit price</th>
                    </tr>
                  </thead>
                  <tbody>
                    {item.purchase.lineItems.map((line, i) => (
                      <tr key={i}>
                        <td>{line.description || "Untitled item"}</td>
                        <td>{line.quantity}</td>
                        <td>{line.unitPrice}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="hint">
                Saved version {item.version} ·{" "}
                {new Date(item.updatedAt).toLocaleString()}
              </p>
              {owner &&
                roles.includes("REQUESTER") &&
                item.state === "DRAFT" && (
                  <button
                    className="secondary"
                    onClick={() => setEditing(true)}
                  >
                    Edit draft
                  </button>
                )}
              {owner && ["REJECTED", "CANCELLED"].includes(item.state) && (
                <button
                  className="secondary"
                  onClick={() => setCorrecting(true)}
                >
                  Create corrected request
                </button>
              )}
            </section>
            <section className="panel">
              <h2>Approval steps</h2>
              <Notice error={members.error} />
              {[0, 1].map((step) => {
                const assignment = item.assignments.find(
                  (a) => a.step === step,
                );
                return (
                  <div className="approval-step" key={step}>
                    <span className="number">0{step + 1}</span>
                    <div>
                      <h3>{step === 0 ? "First review" : "Final review"}</h3>
                      {canAssign && !assignment?.outcome ? (
                        <label>
                          Reviewer for step {step + 1}
                          <select
                            value={selected[step] ?? assignment?.userId ?? ""}
                            onChange={(e) =>
                              setSelected({
                                ...selected,
                                [step]: e.target.value,
                              })
                            }
                          >
                            <option value="">Select reviewer</option>
                            {members.data?.items
                              .filter(
                                (m) =>
                                  m.active &&
                                  m.roles.includes("APPROVER") &&
                                  m.userId !== item.ownerId,
                              )
                              .map((m) => (
                                <option key={m.userId} value={m.userId}>
                                  {m.displayName}
                                </option>
                              ))}
                          </select>
                        </label>
                      ) : (
                        <p>{assignment?.displayName ?? "Not assigned"}</p>
                      )}
                      {assignment?.outcome && (
                        <Status value={assignment.outcome} />
                      )}
                    </div>
                  </div>
                );
              })}
              {canAssign && (
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() =>
                    perform(() =>
                      unwrap(
                        api.PUT(
                          "/api/v1/tenants/{tenantId}/cases/{caseId}/assignments",
                          {
                            params: {
                              path: resource,
                              header: commandHeaders(),
                            },
                            body: {
                              expectedVersion: item.version,
                              approverIds: [0, 1].map(
                                (step) =>
                                  selected[step] ??
                                  item.assignments.find((a) => a.step === step)
                                    ?.userId ??
                                  "",
                              ),
                            },
                          },
                        ),
                      ),
                    )
                  }
                >
                  Save reviewers
                </button>
              )}
              {owner &&
                roles.includes("REQUESTER") &&
                item.state === "DRAFT" && (
                  <button
                    disabled={busy}
                    onClick={() =>
                      perform(() =>
                        unwrap(
                          api.POST(
                            "/api/v1/tenants/{tenantId}/cases/{caseId}/start",
                            {
                              params: {
                                path: resource,
                                header: commandHeaders(),
                              },
                              body: { expectedVersion: item.version },
                            },
                          ),
                        ),
                      )
                    }
                  >
                    Submit for approval
                  </button>
                )}
              {canDecide && (
                <div className="actions">
                  <button disabled={busy} onClick={() => action("APPROVE")}>
                    Approve purchase
                  </button>
                  <button
                    className="danger"
                    disabled={busy}
                    onClick={() => action("REJECT")}
                  >
                    Reject purchase
                  </button>
                </div>
              )}
              {owner &&
                roles.includes("REQUESTER") &&
                ["DRAFT", "ACTIVE"].includes(item.state) && (
                  <button
                    className="text-button"
                    disabled={busy}
                    onClick={() => action("CANCEL")}
                  >
                    Cancel request
                  </button>
                )}
            </section>
          </div>
          {item.state === "APPROVED" && (
            <Documents tenant={tenant} caseId={caseId} canRetry={admin} />
          )}
        </>
      )}
      <Sources
        tenant={tenant}
        caseId={caseId}
        caseVersion={item.version}
        canUpload={
          item.state === "DRAFT" &&
          item.ownerId === userId &&
          roles.includes("REQUESTER")
        }
      />
      <section className="panel">
        <h2>Discussion and audit history</h2>
        {roles.some((r) => ["ADMIN", "REQUESTER", "APPROVER"].includes(r)) && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void action("COMMENT");
            }}
          >
            <label>
              Add a comment
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                maxLength={4000}
                required
              />
            </label>
            <button disabled={busy || !comment.trim()}>Post comment</button>
          </form>
        )}
        <Notice error={history.error} />
        <ol className="audit-list">
          {history.data?.items.map((event) => (
            <li key={event.id}>
              <strong>
                {event.eventType.toLowerCase().replaceAll("_", " ")}
              </strong>
              <time>{new Date(event.createdAt).toLocaleString()}</time>
              {typeof event.details.comment === "string" &&
                event.details.comment && <p>{event.details.comment}</p>}
            </li>
          ))}
        </ol>
        {history.data?.nextCursor && (
          <button
            className="secondary"
            onClick={() => setAuditCursor(history.data!.nextCursor!)}
          >
            Older history
          </button>
        )}
        {auditCursor && (
          <button
            className="text-button"
            onClick={() => setAuditCursor(undefined)}
          >
            Latest history
          </button>
        )}
      </section>
    </>
  );
}
