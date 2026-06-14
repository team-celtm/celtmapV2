"use client";

import Link from "next/link";
import Image from "next/image";
import { useAuth } from "@/contexts/AuthContext";
import AppIcon from "@/components/AppIcon";

export default function TopNav() {
  const { user } = useAuth();

  return (
    <header className="fixed top-0 left-0 w-full z-40 flex justify-between items-center px-8 h-20 bg-white/70 dark:bg-[#131313]/90 backdrop-blur-sm shadow-[0_20px_40px_rgba(0,0,0,0.04)] dark:shadow-[0_20px_40px_rgba(0,0,0,0.3)] border-b border-transparent dark:border-transparent will-change-transform">
      <div className="flex items-center gap-8">
        <span className="text-2xl font-bold tracking-tighter text-indigo-600 dark:text-indigo-400">
          CELTM
        </span>
        <nav className="hidden md:flex gap-6">
          <Link
            href="/dashboard"
            className="font-['Manrope'] font-medium tracking-tight text-slate-500 dark:text-slate-400 hover:text-indigo-500 dark:hover:text-indigo-300 transition-colors duration-300"
          >
            Dashboard
          </Link>
          <Link
            href="/career-aim"
            className="font-['Manrope'] font-medium tracking-tight text-slate-500 dark:text-slate-400 hover:text-indigo-500 dark:hover:text-indigo-300 transition-colors duration-300"
          >
            Career Aim
          </Link>
          <div
            className="font-['Manrope'] font-medium tracking-tight text-slate-300 dark:text-slate-600 cursor-not-allowed italic"
            title="Coming Soon"
          >
            Sessions
          </div>
        </nav>
      </div>
      <div className="flex items-center gap-6">
        <div className="hidden lg:flex items-center gap-4">
          <button className="text-slate-400 hover:text-primary transition-colors" aria-label="Dark mode">
            <AppIcon name="dark_mode" className="h-5 w-5" />
          </button>
          <button className="text-slate-400 hover:text-primary transition-colors" aria-label="Notifications">
            <AppIcon name="notifications" className="h-5 w-5" />
          </button>
        </div>
        <button className="bg-primary text-on-primary px-6 py-2.5 rounded-full text-sm font-semibold tracking-tight hover:opacity-90 active:scale-[0.99] transition-all">
          Skill Profile
        </button>
        <Image
          alt={user?.name ? `${user.name} Avatar` : "User Profile Avatar"}
          className="w-10 h-10 rounded-full border border-transparent dark:border-transparent shadow-sm object-cover"
          src={user?.avatar || "https://ui-avatars.com/api/?name=CELTM+User&background=6366f1&color=fff"}
          width={40}
          height={40}
          unoptimized
          onError={(event) => {
            event.currentTarget.onerror = null;
            event.currentTarget.src = "https://ui-avatars.com/api/?name=CELTM+User&background=6366f1&color=fff";
          }}
        />
      </div>
    </header>
  );
}
