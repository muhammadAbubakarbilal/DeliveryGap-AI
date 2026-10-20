import { RequirementsWorkspace } from "@/components/requirements-workspace";

export default async function Requirements({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RequirementsWorkspace projectId={id} />;
}
