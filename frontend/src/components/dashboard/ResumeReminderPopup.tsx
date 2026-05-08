"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import AppIcon from "@/components/AppIcon";

export function ResumeReminderPopup() {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Check if dismissed in this session or forever
    const isDismissed = localStorage.getItem("celtm_resume_reminder_dismissed");
    if (!isDismissed) {
      // Small delay for better UX
      const timer = setTimeout(() => setIsVisible(true), 2000);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleDismiss = () => {
    setIsVisible(false);
    localStorage.setItem("celtm_resume_reminder_dismissed", "true");
  };

  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 backdrop-blur-xl bg-black/40 animate-in fade-in duration-500">
      <div className="relative w-full max-w-lg bg-white dark:bg-zinc-950 rounded-[40px] shadow-[0_32px_80px_rgba(0,0,0,0.4)] border border-black/5 dark:border-white/10 p-10 overflow-hidden group">
        {/* Background Decorative Element */}
        <div className="absolute -top-24 -right-24 w-64 h-64 bg-primary/5 rounded-full blur-[80px]" />
        
        <div className="relative space-y-8">
          <div className="flex items-center justify-between">
            <div className="h-16 w-16 bg-zinc-900 dark:bg-white rounded-[24px] flex items-center justify-center shadow-lg transform -rotate-6 group-hover:rotate-0 transition-transform duration-500">
              <AppIcon name="upload" className="h-8 w-8 text-white dark:text-zinc-900" />
            </div>
            <button 
              onClick={handleDismiss}
              className="p-2 hover:bg-zinc-100 dark:hover:bg-zinc-900 rounded-full transition-colors"
            >
              <svg className="w-6 h-6 text-zinc-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="space-y-3">
            <h2 className="text-3xl font-black tracking-tight text-zinc-900 dark:text-white leading-[1.1]">
              Elevate Your <br />
              <span className="text-primary">Career Strategy</span>
            </h2>
            <p className="text-zinc-500 dark:text-zinc-400 text-lg leading-relaxed">
              Upload your career artifacts (Resume, Skill Passports, Certs) to unlock hyper-personalized guidance and focus role insights.
            </p>
          </div>

          <div className="pt-2 space-y-4">
            <Link
              href="/settings"
              onClick={handleDismiss}
              className="flex items-center justify-center w-full bg-zinc-950 dark:bg-white text-white dark:text-zinc-950 py-5 rounded-[24px] text-lg font-black shadow-xl hover:scale-[1.02] active:scale-[0.98] transition-all"
            >
              Connect Credentials
            </Link>
            <button
              onClick={handleDismiss}
              className="w-full text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 text-sm font-bold transition-colors py-2"
            >
              Maybe later, show me the dashboard
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
