import AppLayout from "../../components/AppLayout";
import WorkspaceCopilotLoader from "../../components/WorkspaceCopilotLoader";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AppLayout>
      {children}
      <WorkspaceCopilotLoader />
    </AppLayout>
  );
}
