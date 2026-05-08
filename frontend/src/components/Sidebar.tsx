"use client";
import Link from "next/link";
import React from "react";
import { usePathname, useRouter } from "next/navigation";
import { motion as Motion } from "framer-motion";
import { useTheme } from "../contexts/ThemeContext";
import { useAuth } from "../contexts/AuthContext";
import CeltmLogo from "./CeltmLogo";

export default function Sidebar({
  isExpanded = false,
  onToggle,
  onLinkClick,
}: {
  isExpanded?: boolean;
  onToggle?: () => void;
  onLinkClick?: () => void;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();
  const { logout, user } = useAuth();
  const isDark = theme === 'dark';

  const handleLogout = async () => {
    await logout();
    router.push('/login');
  };

  return (
    <aside 
      style={{ width: isExpanded ? 288 : 80 }}
      className={`fixed left-0 top-0 h-full z-[110] flex flex-col pt-10 pb-6 backdrop-blur-sm bg-white/90 dark:bg-[#131313]/95 shadow-[4px_0_28px_rgba(0,0,0,0.03)] dark:shadow-[8px_0_42px_rgba(0,0,0,0.6)] rounded-r-[3rem] hidden xl:flex transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] border-r border-transparent dark:border-transparent [will-change:width]`}
    >
      {/* Header with Logo and Profile */}
      <div className="mb-6 px-4 flex flex-col items-center gap-6">
        <Link href="/dashboard" className="flex items-center justify-center overflow-hidden transition-all duration-500">
            <CeltmLogo compact={!isExpanded} imageClassName="h-8 w-auto" />
        </Link>

        {/* User Profile Trigger */}
        <Link 
          href="/settings"
          className={`relative group flex items-center transition-all duration-300 ${isExpanded ? 'w-full bg-slate-100/50 dark:bg-[#1c1b1b] p-3 rounded-2xl border border-transparent dark:border-transparent shadow-inner dark:shadow-[inset_1px_1px_2px_rgba(255,255,255,0.05)]' : 'justify-center'}`}
        >
          <div className="relative shrink-0">
            <div className={`rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 p-0.5 shadow-lg group-hover:scale-110 transition-transform duration-500 ${isExpanded ? 'w-10 h-10' : 'w-12 h-12'}`}>
                <img 
                  className="w-full h-full rounded-[10px] object-cover bg-surface" 
                  alt={user?.name || "CELTM user"} 
                  src={user?.avatar || "https://ui-avatars.com/api/?name=CELTM+User&background=6366f1&color=fff"}
                  onError={(event) => {
                    event.currentTarget.onerror = null;
                    event.currentTarget.src = "https://ui-avatars.com/api/?name=CELTM+User&background=6366f1&color=fff";
                  }}
                />
            </div>
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-500 border-2 border-white dark:border-[#080808] rounded-full"></div>
          </div>
          {isExpanded && (
            <div className="ml-3 overflow-hidden text-left">
              <p className="text-[11px] font-black text-on-surface truncate">{(user?.name || "CELTM User").toUpperCase()}</p>
              <p className="text-[9px] font-bold text-primary truncate leading-tight uppercase tracking-tighter">{user?.focusRole || "LEARNER"}</p>
            </div>
          )}
        </Link>
        
        {/* Sidebar Toggle Button */}
        <button 
          onClick={onToggle}
          className="w-10 h-10 rounded-full bg-slate-100 dark:bg-[#1c1b1b] text-slate-500 dark:text-slate-300 hover:text-primary transition-all duration-300 flex items-center justify-center group/toggle hover:scale-110 active:scale-95 shadow-sm dark:shadow-[8px_8px_24px_#0a0a0a,-2px_-2px_8px_rgba(255,255,255,0.02)] border border-transparent dark:border-transparent"
        >
          <span className="material-symbols-outlined text-xl transition-transform duration-300" style={{ transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>
            side_navigation
          </span>
        </button>
      </div>

      <nav className="flex-1 space-y-1.5 px-3 flex flex-col items-center overflow-hidden pointer-events-auto">
        {[
            { href: "/dashboard", icon: "grid_view", label: "Dashboard" },
            { href: "/skill-profile", icon: "psychology", label: "Skill Profile" },
            { href: "/hidden-skills", icon: "insights", label: "Hidden Skills" },
            { href: "/learning-paths", icon: "school", label: "Learning Path" },
            { href: "/assessments", icon: "fact_check", label: "Assessments" },
        ].map((item, idx) => {
            const isActive = pathname === item.href;
            return (
              <Link
              key={item.label}
              href={item.href || '#'}
              onClick={() => onLinkClick?.()}
              className={`flex items-center transition-all duration-300 relative group min-h-[52px] rounded-full justify-center ${
                  isActive 
                  ? 'text-primary dark:text-white' 
                  : 'text-slate-400 hover:text-on-surface'
              }`}
              style={{ width: isExpanded ? '100%' : '52px' }}
              >
              {/* Active Background Glow Pill */}
              {isActive && (
                <Motion.div 
                  layoutId="sidebar-active-glow"
                  className="absolute inset-0 bg-primary/10 dark:bg-primary/5 rounded-full border border-primary/20 dark:border-transparent shadow-[0_4px_24px_rgba(30,58,138,0.2)] dark:shadow-[inset_1px_1px_4px_rgba(255,255,255,0.05),0_0_12px_rgba(173,198,255,0.1)]"
                />
              )}
              {/* Hover Background */}
              {!isActive && <div className="absolute inset-0 bg-surface-container-highest dark:bg-white/[0.03] rounded-full opacity-0 group-hover:opacity-100 transition-opacity"></div>}
              
              <div className={`flex items-center gap-3 transition-all duration-500 ${isExpanded ? 'px-6 w-full' : 'w-12 h-12 justify-center'}`}>
                <div className="w-10 h-10 flex items-center justify-center shrink-0 relative z-10 transition-transform duration-300 group-hover:scale-110">
                    <span className="material-symbols-outlined text-xl" >{item.icon}</span> 
                </div>
                {isExpanded && (
                    <span className="font-bold text-[11px] uppercase tracking-[0.1em] relative z-10 whitespace-nowrap">{item.label}</span>
                )}
              </div>
              </Link>
            )
        })}
      </nav>

      <div className="mt-auto px-3 space-y-1.5 py-4 border-t border-slate-200/60 dark:border-transparent">
        {[
          { href: "/settings", icon: "tune", label: "Settings" },
          { action: toggleTheme, icon: isDark ? 'light_mode' : 'dark_mode', label: isDark ? 'Light' : 'Dark' },
          { action: handleLogout, icon: "logout", label: "Log Out", color: "text-red-400" },
        ].map((item) => {
          const handleClick = () => {
            onLinkClick?.();
            if (item.href) {
              router.push(item.href);
            } else if (item.action) {
              item.action();
            }
          };
          return (
            <button
              key={item.label}
              onClick={handleClick}
              className={`flex items-center transition-all duration-300 rounded-full relative group h-12 justify-center ${
                  pathname === item.href 
                  ? 'text-primary dark:text-white' 
                  : 'text-slate-400 hover:text-on-surface'}`}
              style={{ width: isExpanded ? '100%' : '52px' }}
            >
              <div className={`flex items-center transition-all duration-500 ${isExpanded ? 'px-6 w-full gap-3' : 'w-12 h-12 justify-center'}`}>
                  <div className="w-10 h-10 flex items-center justify-center shrink-0 relative z-10 p-2">
                      <span className={`material-symbols-outlined text-xl ${item.color || ''}`}>{item.icon}</span>
                  </div>
                  {isExpanded && (
                      <span className="font-bold text-[11px] uppercase tracking-widest relative z-10 whitespace-nowrap">{item.label}</span>
                  )}
              </div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
