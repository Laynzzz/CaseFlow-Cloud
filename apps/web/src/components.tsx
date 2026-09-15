import type { ReactNode } from "react";

export function Notice({ error }: { error: unknown }) {
  return error ? (
    <p className="notice error" role="alert">
      {error instanceof Error ? error.message : String(error)}
    </p>
  ) : null;
}
export function Empty({ children }: { children: ReactNode }) {
  return <p className="empty">{children}</p>;
}
export function Status({ value }: { value: string }) {
  return (
    <span className={`status-pill ${value.toLowerCase()}`}>
      {value.toLowerCase().replaceAll("_", " ")}
    </span>
  );
}
