import createClient from "openapi-fetch";
import type { paths } from "./schema";
import { auth } from "../auth";

export const api = createClient<paths>({ baseUrl: "" });
api.use({
  async onRequest({ request }) {
    if (auth.authenticated) {
      await auth.updateToken(30);
      request.headers.set("Authorization", `Bearer ${auth.token}`);
    }
    return request;
  },
});

export async function unwrap<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await promise;
  if (!response.ok || data === undefined) {
    const problem = error as { detail?: string } | undefined;
    throw new Error(
      problem?.detail ??
        `Request failed (${response.status}). Please try again.`,
    );
  }
  return data;
}
export const commandHeaders = () => ({
  "Idempotency-Key": crypto.randomUUID(),
});
