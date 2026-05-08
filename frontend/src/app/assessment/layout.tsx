import AuthBackdrop from "@/components/auth/AuthBackdrop";

export default function AssessmentLayout({ children }: { children: React.ReactNode }) {
  return <AuthBackdrop>{children}</AuthBackdrop>;
}
