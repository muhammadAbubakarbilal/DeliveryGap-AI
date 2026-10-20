import { SourceWorkspace } from "@/components/source-workspace";

export default async function Document({ params }: { params: Promise<{ id: string; documentId: string }> }) {
  const { id, documentId } = await params;
  return <SourceWorkspace projectId={id} documentId={documentId} />;
}
