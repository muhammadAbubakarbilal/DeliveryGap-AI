import { Shell } from "@/components/shell";
import { requireSession } from "@/lib/server-api";
export default async function WorkspaceLayout({ children }: { children: React.ReactNode }) {
  const session = await requireSession();
  return <Shell session={session}>{children}</Shell>;
}
