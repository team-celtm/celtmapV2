"use client";

import dynamic from "next/dynamic";

const WorkspaceCopilot = dynamic(() => import("./WorkspaceCopilot"), {
  ssr: false,
  loading: () => null,
});

export default function WorkspaceCopilotLoader() {
  return <WorkspaceCopilot />;
}
