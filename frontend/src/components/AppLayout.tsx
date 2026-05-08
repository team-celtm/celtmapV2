"use client";
import React, { useEffect, useState } from "react";
import Sidebar from "./Sidebar";
import AbstractBackground from "./AbstractBackground";
import { motion as Motion } from "framer-motion";
import { useTheme } from "../contexts/ThemeContext";
import { useAuth } from "../contexts/AuthContext";
import { useRouter } from "next/navigation";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [isSidebarPinned, setIsSidebarPinned] = useState(false);
  const [isSidebarHovered, setIsSidebarHovered] = useState(false);
  const { theme } = useTheme();
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const isDark = theme === 'dark';
  const isSidebarExpanded = isSidebarPinned || isSidebarHovered;
  
  // Dashboard access now only requires onboarding completion.
  // Placement completion is optional for viewing the dashboard.
  const hasAccess = Boolean(
    user && user.hasCompletedOnboarding
  );

  useEffect(() => {
    if (isLoading) {
      return;
    }

    if (!user) {
      router.replace("/login");
      return;
    }

    if (!user.hasCompletedOnboarding) {
      router.replace("/onboarding");
      return;
    }

    // Relaxed Guard: We no longer force users to /assessment if they are in the dashboard.
    // This prevents the locked-door loop.
    if (!user.hasCompletedPlacement) {
       console.log("User has not completed placement, but we allow dashboard access now.");
    }
  }, [isLoading, router, user]);

  if (!hasAccess || isLoading) {
    return (
      <div className={`flex min-h-screen items-center justify-center ${isDark ? 'dark-abstract-bg' : 'bg-white'}`}>
        <div className="h-10 w-10 rounded-full border-2 border-slate-300 dark:border-transparent border-t-google-blue animate-spin" />
      </div>
    );
  }

  return (
    <div className={`flex min-h-screen relative overflow-hidden transition-colors duration-500 ${isDark ? 'dark-abstract-bg' : 'bg-white'}`}>
      <AbstractBackground />
      <div
        className="h-full z-[110]"
        onMouseEnter={() => setIsSidebarHovered(true)}
        onMouseLeave={() => setIsSidebarHovered(false)}
      >
        <Sidebar
          isExpanded={isSidebarExpanded}
          onToggle={() => setIsSidebarPinned((current) => !current)}
          onLinkClick={() => setIsSidebarPinned(false)}
        />
      </div>
      <Motion.main 
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        style={{ 
          paddingLeft: isSidebarExpanded ? 288 : 80,
          transition: "padding-left 320ms cubic-bezier(0.22, 1, 0.36, 1)",
          willChange: "padding-left"
        }}
        className="flex-1 relative"
      >
        <div className="w-full h-full pt-3 px-3 md:px-4 lg:px-5 pb-6 overflow-x-hidden">
          {children}
        </div>
      </Motion.main>
    </div>
  );
}
