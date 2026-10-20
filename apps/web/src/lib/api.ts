import type { components } from "./api-types";

export type User = components["schemas"]["UserOut"];
export type Session = components["schemas"]["SessionOut"];
export type Project = components["schemas"]["ProjectOut"];
export type ProjectPage = components["schemas"]["ProjectPage"];
export type Member = components["schemas"]["MemberOut"];

export class ApiError extends Error {
  constructor(public status: number, message: string, public requestId?: string) {
    super(message);
  }
}

export async function api<T>(path: string, options: RequestInit = {}, csrf?: string): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    cache: "no-store",
    credentials: "same-origin",
    headers: { ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(csrf ? { "X-CSRF-Token": csrf } : {}), ...options.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    if (response.status === 401 && path !== "/auth/login" && path !== "/auth/neon") window.location.replace("/login");
    throw new ApiError(response.status, body?.error?.message ?? "The service is unavailable. Please try again.", body?.error?.request_id);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function message(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}
