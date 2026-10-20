import { EvidenceWorkspace } from "@/components/evidence-workspace";

export default async function EvidencePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <EvidenceWorkspace projectId={id} />;
}
