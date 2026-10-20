import { AnalysisWorkspace } from "@/components/analysis-workspace";

export default async function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AnalysisWorkspace projectId={id} />;
}
