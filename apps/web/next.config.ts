import type { NextConfig } from "next";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

// Neon writes the monorepo root env; Next normally reads only apps/web.
for (const name of [".env.local", ".env"]) {
  const file = resolve(process.cwd(), "../..", name);
  if (existsSync(file)) process.loadEnvFile(file);
}

const config: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${process.env.INTERNAL_API_URL ?? "http://127.0.0.1:8000"}/api/v1/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "same-origin" },
      { key: "X-Frame-Options", value: "DENY" },
    ] }];
  },
};
export default config;
