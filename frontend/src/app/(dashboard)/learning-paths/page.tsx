import Link from "next/link";

export default function LearningPathsDisabledPage() {
  return (
    <div className="mx-auto flex min-h-[70vh] w-full max-w-3xl items-center justify-center px-5">
      <section className="clay-card rounded-[36px] p-8 text-center">
        <p className="text-[11px] font-black uppercase tracking-[0.24em] text-primary">Phase 1 update</p>
        <h1 className="mt-3 text-3xl font-black tracking-tight text-on-surface">Roadmap UI is paused</h1>
        <p className="mt-4 text-sm leading-7 text-on-surface-variant">
          The old roadmap section has been removed from the main flow. Use Career Aim for saved AI inference and next-step guidance.
        </p>
        <Link
          href="/career-aim"
          className="mt-6 inline-flex rounded-full bg-primary px-6 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-white"
        >
          Open Career Aim
        </Link>
      </section>
    </div>
  );
}
