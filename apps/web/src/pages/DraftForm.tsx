import { useRef, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { api, unwrap, commandHeaders } from "../api/client";
import type { components } from "../api/schema";
import { Notice } from "../components";
type Case = components["schemas"]["Case"];
type Form = components["schemas"]["PurchaseInput"] & { workflowId: string };
const number = z
  .string()
  .regex(/^\d+(\.\d{1,4})?$/, "Enter a nonnegative decimal amount");
const purchaseSchema = z.object({
  vendor: z.string().max(200),
  description: z.string().max(2000),
  currency: z.string().regex(/^[A-Z]{3}$/, "Use a three-letter currency code"),
  costCenter: z.string().max(100),
  justification: z.string().max(4000),
  lineItems: z
    .array(
      z.object({
        description: z.string().max(500),
        quantity: number.refine(
          (v) => Number(v) > 0,
          "Quantity must be positive",
        ),
        unitPrice: number,
      }),
    )
    .max(100),
});
export function DraftForm({
  tenant,
  existing,
  originalCaseId,
  onSaved,
}: {
  tenant: string;
  existing?: Case;
  originalCaseId?: string;
  onSaved?: (item: Case) => void;
}) {
  const navigate = useNavigate(),
    cache = useQueryClient();
  const [error, setError] = useState<unknown>();
  const initialVersion = useRef(existing?.version);
  const pending = useRef<{
    body: string;
    headers: ReturnType<typeof commandHeaders>;
  } | null>(null);
  const workflows = useQuery({
    queryKey: ["workflows", tenant],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/tenants/{tenantId}/workflows", {
          params: { path: { tenantId: tenant } },
        }),
      ),
  });
  const {
    register,
    control,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<Form>({
    defaultValues: {
      vendor: existing?.purchase.vendor ?? "",
      description: existing?.purchase.description ?? "",
      currency: existing?.purchase.currency ?? "USD",
      costCenter: existing?.purchase.costCenter ?? "",
      justification: existing?.purchase.justification ?? "",
      lineItems: existing?.purchase.lineItems ?? [
        { description: "", quantity: "1", unitPrice: "0.00" },
      ],
      workflowId: existing?.workflowId ?? "",
    },
  });
  const { fields, append, remove } = useFieldArray({
    control,
    name: "lineItems",
  });
  async function save(values: Form) {
    setError(undefined);
    const parsed = purchaseSchema.safeParse(values);
    if (!parsed.success) {
      setError(parsed.error.issues.map((i) => i.message).join("; "));
      return;
    }
    try {
      const body = {
        purchase: parsed.data,
        workflowId: values.workflowId || null,
        ...(originalCaseId ? { originalCaseId } : {}),
        ...(existing && !originalCaseId
          ? { expectedVersion: initialVersion.current }
          : {}),
      };
      const serialized = JSON.stringify(body);
      if (pending.current?.body !== serialized)
        pending.current = { body: serialized, headers: commandHeaders() };
      const headers = pending.current.headers;
      const item =
        existing && !originalCaseId
          ? await unwrap(
              api.PUT("/api/v1/tenants/{tenantId}/cases/{caseId}", {
                params: {
                  path: { tenantId: tenant, caseId: existing.id },
                  header: headers,
                },
                body,
              }),
            )
          : await unwrap(
              api.POST("/api/v1/tenants/{tenantId}/cases", {
                params: { path: { tenantId: tenant }, header: headers },
                body,
              }),
            );
      await cache.invalidateQueries({ queryKey: ["cases", tenant] });
      if (onSaved) onSaved(item);
      else navigate(`/cases/${item.id}`);
    } catch (e) {
      setError(e);
    }
  }
  return (
    <form className="panel form" onSubmit={handleSubmit(save)}>
      <Notice error={error} />
      <Notice error={workflows.error} />
      <p className="hint">
        Save your work as a draft. Required purchase details and reviewer
        assignments are checked before submission.
      </p>
      <div className="form-grid">
        <label>
          Vendor
          <input {...register("vendor")} maxLength={200} />
        </label>
        <label>
          Purchase description
          <input {...register("description")} maxLength={2000} />
        </label>
        <label>
          Currency
          <input {...register("currency")} maxLength={3} required />
        </label>
        <label>
          Cost center
          <input {...register("costCenter")} maxLength={100} />
        </label>
      </div>
      <label>
        Why is this purchase needed?
        <textarea {...register("justification")} rows={3} maxLength={4000} />
      </label>
      <fieldset>
        <legend>Line items</legend>
        {fields.map((field, index) => (
          <div className="line-item" key={field.id}>
            <label>
              Description
              <input
                {...register(`lineItems.${index}.description`)}
                maxLength={500}
              />
            </label>
            <label>
              Quantity
              <input
                {...register(`lineItems.${index}.quantity`)}
                inputMode="decimal"
                required
              />
            </label>
            <label>
              Unit price
              <input
                {...register(`lineItems.${index}.unitPrice`)}
                inputMode="decimal"
                required
              />
            </label>
            <button
              className="secondary"
              type="button"
              aria-label={`Remove item ${index + 1}`}
              onClick={() => remove(index)}
            >
              Remove
            </button>
          </div>
        ))}
        <button
          className="secondary"
          type="button"
          disabled={fields.length >= 100}
          onClick={() =>
            append({ description: "", quantity: "1", unitPrice: "0.00" })
          }
        >
          Add line item
        </button>
      </fieldset>
      <label>
        Approval workflow
        <select {...register("workflowId")}>
          <option value="">Select a published workflow</option>
          {workflows.data?.items
            .filter((w) => w.published)
            .map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
        </select>
      </label>
      <p className="hint">The server calculates the total when you save.</p>
      <button disabled={isSubmitting}>
        {isSubmitting ? "Saving…" : "Save draft"}
      </button>
    </form>
  );
}
