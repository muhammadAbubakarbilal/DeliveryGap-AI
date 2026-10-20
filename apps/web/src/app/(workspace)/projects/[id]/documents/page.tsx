import { SourceWorkspace } from "@/components/source-workspace";

export default async function Documents({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SourceWorkspace projectId={id} />;
}
