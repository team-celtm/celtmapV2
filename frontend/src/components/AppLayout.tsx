"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import Sidebar from "./Sidebar";
import AbstractBackground from "./AbstractBackground";
import { AnimatePresence, motion as Motion } from "framer-motion";
import { useTheme } from "../contexts/ThemeContext";
import { useAuth } from "../contexts/AuthContext";
import { useRouter, usePathname } from "next/navigation";
import Chatbot from "./Chatbot";
import CeltmProgressLoader from "./CeltmProgressLoader";
import CeltmLogo from "./CeltmLogo";
import AppIcon from "./AppIcon";

const NAV_ITEMS = [
  { href: "/dashboard", icon: "grid_view", label: "Dashboard" },
  { href: "/skill-profile", icon: "psychology", label: "Skill Profile" },
  { href: "/hidden-skills", icon: "insights", label: "Hidden Skills" },
  { href: "/assessments", icon: "fact_check", label: "Assessments" },
  { href: "/career-aim", icon: "route", label: "Career Aim" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [isSidebarPinned, setIsSidebarPinned] = useState(false);
  const [isSidebarHovered, setIsSidebarHovered] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isCompactNav, setIsCompactNav] = useState(() =>
    typeof window === "undefined" ? false : window.matchMedia("(max-width: 1279px)").matches,
  );
  const { theme, toggleTheme } = useTheme();
  const { user, isLoading, isLoggingOut, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const isDark = theme === 'dark';
  const isSidebarExpanded = !isCompactNav && (isSidebarPinned || isSidebarHovered);
  
  const hasAccess = Boolean(user);
  const isQuiz = pathname?.includes("/assessments/quiz");
  const isWrittenAssessment = pathname?.includes("/assessments/written-protocol");
  const isAssessmentCanvas = isQuiz || isWrittenAssessment;
  const sidebarOffset = isAssessmentCanvas || isCompactNav ? 0 : isSidebarExpanded ? 288 : 80;

  useEffect(() => {
    const query = window.matchMedia("(max-width: 1279px)");
    const syncCompactNav = () => setIsCompactNav(query.matches);
    syncCompactNav();
    query.addEventListener("change", syncCompactNav);
    return () => query.removeEventListener("change", syncCompactNav);
  }, []);

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (isLoading) {
      return;
    }

    if (!user) {
      router.replace("/login");
      return;
    }

  }, [isLoading, router, user]);

  const handleMobileLogout = async () => {
    await logout();
    setIsMobileMenuOpen(false);
    router.push("/login");
  };

  if (isLoggingOut) {
    return (
      <div className={`flex min-h-screen items-center justify-center ${isDark ? 'dark-abstract-bg' : 'bg-white'}`}>
        <CeltmProgressLoader
          title="See you soon"
          caption="Logging out"
          minHeightClassName="min-h-screen"
          stages={["Clearing session", "Securing account", "Redirecting"]}
        />
      </div>
    );
  }

  if (!hasAccess || isLoading) {
    return (
      <div className={`flex min-h-screen items-center justify-center ${isDark ? 'dark-abstract-bg' : 'bg-white'}`}>
        <CeltmProgressLoader
          title="Opening CELTM"
          caption="Cooking your workspace"
          minHeightClassName="min-h-screen"
          stages={["Checking your session", "Loading workspace access", "Preparing dashboard routes", "Opening your workspace"]}
        />
      </div>
    );
  }

  return (
    <div className={`flex min-h-screen relative overflow-hidden transition-colors duration-500 ${isDark ? 'dark-abstract-bg' : 'bg-white'}`}>
      <AbstractBackground />
      {!isAssessmentCanvas && isCompactNav ? (
        <CompactNavigation
          isOpen={isMobileMenuOpen}
          onOpenChange={setIsMobileMenuOpen}
          onToggleTheme={toggleTheme}
          onLogout={handleMobileLogout}
          pathname={pathname ?? "/dashboard"}
          theme={theme}
          userName={user?.name || "CELTM User"}
        />
      ) : null}
      {!isAssessmentCanvas && (
        <div
          className="h-full z-[110] hidden xl:block"
          onMouseEnter={() => {
            if (!isCompactNav) setIsSidebarHovered(true);
          }}
          onMouseLeave={() => {
            if (!isCompactNav) setIsSidebarHovered(false);
          }}
        >
          <Sidebar
            isExpanded={isSidebarExpanded}
            onToggle={() => setIsSidebarPinned((current) => !current)}
            onLinkClick={() => setIsSidebarPinned(false)}
          />
        </div>
      )}
      <Motion.main 
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        style={{ 
          paddingLeft: sidebarOffset,
          transition: "padding-left 320ms cubic-bezier(0.22, 1, 0.36, 1)",
          willChange: "padding-left"
        }}
        className="flex-1 relative min-w-0"
      >
        <div className={`w-full h-full px-3 pb-6 md:px-4 lg:px-5 overflow-x-hidden ${!isAssessmentCanvas && isCompactNav ? "pt-24" : "pt-3"}`}>
          {children}
        </div>
      </Motion.main>
      {!isAssessmentCanvas && <Chatbot />}
    </div>
  );
}

function CompactNavigation({
  isOpen,
  onOpenChange,
  onToggleTheme,
  onLogout,
  pathname,
  theme,
  userName,
}: {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  onToggleTheme: () => void;
  onLogout: () => Promise<void>;
  pathname: string;
  theme: "light" | "dark";
  userName: string;
}) {
  const activeItem = NAV_ITEMS.find((item) => pathname === item.href || pathname.startsWith(`${item.href}/`));

  return (
    <>
      <header className="fixed left-3 right-3 top-3 z-[130] flex h-16 items-center justify-between rounded-[2rem] border border-white/80 bg-white/92 px-3 shadow-[0_18px_44px_rgba(15,23,42,0.10)] backdrop-blur-xl dark:border-transparent dark:bg-[#131313]/95 dark:shadow-[0_18px_44px_rgba(0,0,0,0.45)] sm:left-4 sm:right-4 sm:px-4">
        <Link href="/dashboard" className="flex min-w-0 items-center gap-3">
          <CeltmLogo compact className="h-9 w-10 shrink-0" imageClassName="h-8 w-auto" />
          <div className="min-w-0">
            <p className="truncate text-[10px] font-black uppercase tracking-[0.2em] text-primary">
              {activeItem?.label || "CELTM"}
            </p>
            <p className="truncate text-xs font-bold text-on-surface-variant">{userName}</p>
          </div>
        </Link>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToggleTheme}
            className="flex h-11 w-11 items-center justify-center rounded-full bg-surface-container text-on-surface-variant transition hover:text-primary"
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
          >
            <AppIcon name={theme === "dark" ? "light_mode" : "dark_mode"} className="h-5 w-5" />
          </button>
          <button
            type="button"
            onClick={() => onOpenChange(!isOpen)}
            className="flex h-11 w-11 items-center justify-center rounded-full bg-primary text-white shadow-lg shadow-primary/20 transition active:scale-95"
            aria-label="Open navigation menu"
            aria-expanded={isOpen}
          >
            <AppIcon name={isOpen ? "close" : "panel_left_open"} className="h-5 w-5" />
          </button>
        </div>
      </header>

      <AnimatePresence>
        {isOpen ? (
          <>
            <Motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-[125] bg-slate-950/35 backdrop-blur-sm xl:hidden"
              onClick={() => onOpenChange(false)}
            />
            <Motion.nav
              initial={{ opacity: 0, y: -14, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -12, scale: 0.98 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              className="fixed left-3 right-3 top-24 z-[131] rounded-[2rem] border border-white/80 bg-white p-3 shadow-[0_28px_80px_rgba(15,23,42,0.22)] dark:border-transparent dark:bg-[#131313] sm:left-4 sm:right-4"
            >
              <div className="grid gap-2 sm:grid-cols-2">
                {NAV_ITEMS.map((item) => {
                  const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => onOpenChange(false)}
                      className={`flex min-h-14 items-center gap-3 rounded-2xl px-4 py-3 transition ${
                        isActive
                          ? "border border-primary/20 bg-primary/10 text-primary"
                          : "border border-outline-variant/10 bg-surface-container-low text-on-surface-variant hover:text-on-surface"
                      }`}
                    >
                      <AppIcon name={item.icon} className="h-5 w-5 shrink-0" />
                      <span className="text-xs font-black uppercase tracking-[0.16em]">{item.label}</span>
                    </Link>
                  );
                })}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <Link
                  href="/settings"
                  onClick={() => onOpenChange(false)}
                  className="flex h-12 items-center justify-center gap-2 rounded-2xl bg-surface-container-high text-[10px] font-black uppercase tracking-[0.16em] text-on-surface"
                >
                  <AppIcon name="tune" className="h-4 w-4" />
                  Settings
                </Link>
                <button
                  type="button"
                  onClick={() => void onLogout()}
                  className="flex h-12 items-center justify-center gap-2 rounded-2xl bg-red-500/10 text-[10px] font-black uppercase tracking-[0.16em] text-red-500"
                >
                  <AppIcon name="logout" className="h-4 w-4" />
                  Log out
                </button>
              </div>
            </Motion.nav>
          </>
        ) : null}
      </AnimatePresence>
    </>
  );
}
