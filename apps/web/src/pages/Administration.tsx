import { useState } from "react";
import { Templates } from "./Templates";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, commandHeaders } from "../api/client";
import { Empty, Notice, Status } from "../components";
import type { components } from "../api/schema";
type Role = components["schemas"]["Membership"]["roles"][number];
const roleOptions: Role[] = ["ADMIN", "REQUESTER", "APPROVER", "AUDITOR"];
export function Administration({ tenant }: { tenant: string }) {
  const cache = useQueryClient();
  const [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false);
  const [userId, setUserId] = useState(""),
    [role, setRole] = useState<Role>("APPROVER"),
    [name, setName] = useState(""),
    [first, setFirst] = useState("Manager review"),
    [second, setSecond] = useState("Finance review");
  const members = useQuery({
    queryKey: ["members", tenant],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/memberships", {
          params: { path: { tenantId: tenant } },
        }),
      ),
  });
  const workflows = useQuery({
    queryKey: ["workflows", tenant],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/workflows", {
          params: { path: { tenantId: tenant } },
        }),
      ),
  });
  async function perform(work: () => Promise<unknown>) {
    setError(undefined);
    setBusy(true);
    try {
      await work();
      await cache.invalidateQueries({ queryKey: ["members", tenant] });
      await cache.invalidateQueries({ queryKey: ["workflows", tenant] });
      await cache.invalidateQueries({ queryKey: ["me"] });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const saveMember = (
    member: components["schemas"]["Membership"],
    roles: Role[],
    active: boolean,
  ) =>
    perform(() =>
      unwrap(
        api.PUT("/api/v1/tenants/{tenantId}/memberships", {
          params: { path: { tenantId: tenant }, header: commandHeaders() },
          body: {
            userId: member.userId,
            roles,
            active,
            expectedVersion: member.version,
          },
        }),
      ),
    );
  return (
    <>
      <div className="page-title">
        <div>
          <p className="eyebrow">Organization settings</p>
          <h1>Administration</h1>
        </div>
      </div>
      <Notice error={error} />
      <section className="panel">
        <h2>Members and roles</h2>
        <p>
          Ask a person to sign in first and share the member ID shown in their
          account menu.
        </p>
        <form
          className="inline-form"
          onSubmit={(e) => {
            e.preventDefault();
            void perform(async () => {
              await unwrap(
                api.PUT("/api/v1/tenants/{tenantId}/memberships", {
                  params: {
                    path: { tenantId: tenant },
                    header: commandHeaders(),
                  },
                  body: { userId, roles: [role], active: true },
                }),
              );
              setUserId("");
            });
          }}
        >
          <label>
            Known member ID
            <input
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              required
            />
          </label>
          <label>
            Initial role
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
            >
              {roleOptions.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </label>
          <button disabled={busy}>Add member</button>
        </form>
        <Notice error={members.error} />
        {members.isPending ? (
          <Empty>Loading members…</Empty>
        ) : (
          <div className="member-list">
            {members.data?.items.map((m) => (
              <div className="member" key={m.userId}>
                <div>
                  <strong>{m.displayName}</strong>
                  <p className="hint">{m.active ? "Active" : "Deactivated"}</p>
                </div>
                <div className="role-checks">
                  {roleOptions.map((r) => (
                    <label className="check" key={r}>
                      <input
                        type="checkbox"
                        checked={m.roles.includes(r)}
                        disabled={
                          busy || (m.roles.length === 1 && m.roles.includes(r))
                        }
                        onChange={(e) =>
                          saveMember(
                            m,
                            e.target.checked
                              ? [...m.roles, r]
                              : m.roles.filter((v) => v !== r),
                            m.active,
                          )
                        }
                      />
                      {r.toLowerCase()}
                    </label>
                  ))}
                </div>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => saveMember(m, m.roles, !m.active)}
                >
                  {m.active ? "Deactivate" : "Reactivate"}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
      <section className="panel">
        <h2>Versioned approval workflows</h2>
        <p>
          Published versions stay unchanged for historical requests. Create a
          new draft to introduce a different workflow.
        </p>
        <form
          className="form"
          onSubmit={(e) => {
            e.preventDefault();
            void perform(async () => {
              await unwrap(
                api.POST("/api/v1/tenants/{tenantId}/workflows", {
                  params: {
                    path: { tenantId: tenant },
                    header: commandHeaders(),
                  },
                  body: { name, steps: [first, second] },
                }),
              );
              setName("");
            });
          }}
        >
          <div className="form-grid">
            <label>
              Workflow name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={120}
                required
              />
            </label>
            <label>
              Step 1 label
              <input
                value={first}
                onChange={(e) => setFirst(e.target.value)}
                maxLength={80}
                required
              />
            </label>
            <label>
              Step 2 label
              <input
                value={second}
                onChange={(e) => setSecond(e.target.value)}
                maxLength={80}
                required
              />
            </label>
          </div>
          <button disabled={busy}>Create draft workflow</button>
        </form>
        <Notice error={workflows.error} />
        <div className="member-list">
          {workflows.data?.items.map((w) => (
            <div className="member" key={w.id}>
              <div>
                <strong>{w.name}</strong>
                <p>{w.steps.join(" → ")}</p>
              </div>
              <Status value={w.published ? "PUBLISHED" : "DRAFT"} />
              {!w.published && (
                <button
                  disabled={busy}
                  onClick={() =>
                    perform(() =>
                      unwrap(
                        api.POST(
                          "/api/v1/tenants/{tenantId}/workflows/{workflowId}/publish",
                          {
                            params: {
                              path: { tenantId: tenant, workflowId: w.id },
                              header: commandHeaders(),
                            },
                            body: { expectedVersion: w.version },
                          },
                        ),
                      ),
                    )
                  }
                >
                  Publish version
                </button>
              )}
            </div>
          ))}
        </div>
      </section>
      <Templates tenant={tenant} />
    </>
  );
}
