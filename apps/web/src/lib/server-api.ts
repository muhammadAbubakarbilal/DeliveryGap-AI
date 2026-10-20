import "server-only";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { Session } from "./api";

export async function requireSession(): Promise<Session> {
  const jar = await cookies();
  const token = jar.get("deliverygap_session");
  if (!token) redirect("/login");
  const response = await fetch(`${process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000"}/api/v1/auth/me`, {
    headers: { Cookie: `deliverygap_session=${encodeURIComponent(token.value)}` }, cache: "no-store",
  });
  if (response.status === 401) redirect("/login");
  if (!response.ok) throw new Error("The API is unavailable. Check the backend connection.");
  return response.json() as Promise<Session>;
}
