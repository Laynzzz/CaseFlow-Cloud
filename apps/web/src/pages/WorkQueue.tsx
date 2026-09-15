import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, unwrap } from "../api/client";
import { Notice, Empty, Status } from "../components";
type State = "DRAFT" | "ACTIVE" | "APPROVED" | "REJECTED" | "CANCELLED";
export function WorkQueue({
  tenant,
  canRequest,
}: {
  tenant: string;
  canRequest: boolean;
}) {
  const [state, setState] = useState<State | "">("");
  const [mine, setMine] = useState(false);
  const [cursors, setCursors] = useState<(string | undefined)[]>([undefined]);
  const cursor = cursors[cursors.length - 1];
  const cases = useQuery({
    queryKey: ["cases", tenant, state, mine, cursor],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/cases", {
          params: {
            path: { tenantId: tenant },
            query: {
              state: state || undefined,
              assignedToMe: mine,
              cursor,
              limit: 15,
            },
          },
        }),
      ),
  });
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">Purchasing workspace</p>
          <h1>Purchase requests</h1>
          <p>Keep decisions moving, one review at a time.</p>
        </div>
        {canRequest && (
          <Link className="button" to="/new">
            New purchase request
          </Link>
        )}
      </div>
      <div className="filters">
        <label>
          Status
          <select
            value={state}
            onChange={(e) => {
              setState(e.target.value as State | "");
              setCursors([undefined]);
            }}
          >
            <option value="">All requests</option>
            {["DRAFT", "ACTIVE", "APPROVED", "REJECTED", "CANCELLED"].map(
              (s) => (
                <option key={s}>{s}</option>
              ),
            )}
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={mine}
            onChange={(e) => {
              setMine(e.target.checked);
              setCursors([undefined]);
            }}
          />
          Assigned to me
        </label>
      </div>
      <Notice error={cases.error} />
      {cases.isPending ? (
        <Empty>Loading requests…</Empty>
      ) : cases.data?.items.length === 0 ? (
        <Empty>No requests match these filters.</Empty>
      ) : (
        <div className="request-list">
          {cases.data?.items.map((item) => (
            <Link
              className="request-card"
              to={`/cases/${item.id}`}
              key={item.id}
            >
              <div>
                <span className="eyebrow">
                  {item.purchase.vendor || "Vendor not entered"}
                </span>
                <h2>{item.purchase.description || "Untitled purchase"}</h2>
                <p>
                  {new Date(item.createdAt).toLocaleDateString()} ·{" "}
                  {item.assignments.length} reviewers assigned
                </p>
              </div>
              <div className="request-summary">
                <strong>
                  {item.purchase.currency} {item.purchase.total}
                </strong>
                <Status value={item.state} />
              </div>
            </Link>
          ))}
        </div>
      )}
      <div className="pagination">
        <button
          className="secondary"
          disabled={cursors.length === 1}
          onClick={() => setCursors(cursors.slice(0, -1))}
        >
          Previous
        </button>
        <button
          className="secondary"
          disabled={!cases.data?.nextCursor}
          onClick={() => setCursors([...cursors, cases.data!.nextCursor!])}
        >
          Next
        </button>
      </div>
    </>
  );
}
