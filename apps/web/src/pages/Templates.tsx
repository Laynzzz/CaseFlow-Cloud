import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, commandHeaders } from "../api/client";
import { auth } from "../auth";
import { Notice, Status } from "../components";

export function Templates({ tenant }: { tenant: string }) {
  const cache = useQueryClient();
  const [name, setName] = useState(""),
    [file, setFile] = useState<File>();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>();
  const templates = useQuery({
    queryKey: ["templates", tenant],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/templates", {
          params: { path: { tenantId: tenant } },
        }),
      ),
  });
  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    if (
      !file.name.toLowerCase().endsWith(".docx") ||
      file.size > 10 * 1024 * 1024 ||
      file.size === 0
    ) {
      setError("Choose a DOCX file up to 10 MB.");
      return;
    }
    setBusy(true);
    setError(undefined);
    try {
      const template = await unwrap(
        api.POST("/api/v1/tenants/{tenantId}/templates", {
          params: { path: { tenantId: tenant }, header: commandHeaders() },
          body: { name, byteSize: file.size },
        }),
      );
      await auth.updateToken(30);
      const response = await fetch(
        `/api/v1/tenants/${tenant}/templates/${template.id}/content`,
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
        throw new Error("The file upload failed. Please try again.");
      await unwrap(
        api.POST("/api/v1/tenants/{tenantId}/templates/{templateId}/finalize", {
          params: {
            path: { tenantId: tenant, templateId: template.id },
            header: commandHeaders(),
          },
          body: { expectedVersion: template.version },
        }),
      );
      setName("");
      setFile(undefined);
      await cache.invalidateQueries({ queryKey: ["templates", tenant] });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>Document templates</h2>
      <p>
        Upload a Word template, validate it, then publish it for new requests.
        Published files stay fixed for the purchases that use them.
      </p>
      <Notice error={error} />
      <Notice error={templates.error} />
      <form onSubmit={upload}>
        <label>
          Template name
          <input
            required
            maxLength={120}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </label>
        <label>
          Word template (.docx, up to 10 MB)
          <input
            type="file"
            accept=".docx"
            onChange={(e) => setFile(e.target.files?.[0])}
          />
        </label>
        <p className="hint">
          Supported placeholders:{" "}
          {
            "{{ vendor }}, {{ description }}, {{ currency }}, {{ total }}, {{ cost_center }}, {{ justification }}, {{ line_items }}, {{ approved_at }}, {{ case_id }}, {{ approvers }}"
          }
          . Keep each placeholder together in one text run. External links and
          embedded objects are not supported.
        </p>
        <button disabled={busy || !file}>
          {busy ? "Validating template…" : "Upload and validate"}
        </button>
      </form>
      <div className="member-list">
        {templates.data?.items.map((t) => (
          <div className="member" key={t.id}>
            <div>
              <strong>{t.name}</strong>
              <p>
                {Math.ceil(t.byteSize / 1024)} KB · version {t.version}
              </p>
            </div>
            <Status value={t.state} />
            {t.state === "VALIDATED" && (
              <button
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(undefined);
                  try {
                    await unwrap(
                      api.POST(
                        "/api/v1/tenants/{tenantId}/templates/{templateId}/publish",
                        {
                          params: {
                            path: { tenantId: tenant, templateId: t.id },
                            header: commandHeaders(),
                          },
                          body: { expectedVersion: t.version },
                        },
                      ),
                    );
                    await cache.invalidateQueries({
                      queryKey: ["templates", tenant],
                    });
                  } catch (e) {
                    setError(e);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Publish template
              </button>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
