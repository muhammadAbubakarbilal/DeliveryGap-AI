import { createNeonAuth } from "@neondatabase/auth/next/server";
import type { NextRequest } from "next/server";

type Context = { params: Promise<{ path: string[] }> };

async function handle(request: NextRequest, context: Context) {
  const baseUrl = process.env.NEON_AUTH_BASE_URL;
  const secret = process.env.NEON_AUTH_COOKIE_SECRET;
  if (!baseUrl || !secret) {
    return Response.json({ message: "Neon Auth is not configured" }, { status: 503 });
  }
  const handlers = createNeonAuth({ baseUrl, cookies: { secret }, logLevel: "silent" }).handler();
  const method = request.method as keyof typeof handlers;
  const handler = handlers[method];
  if (!handler) return new Response(null, { status: 405 });
  return handler(request, context);
}

export { handle as GET, handle as POST, handle as PUT, handle as DELETE, handle as PATCH };
