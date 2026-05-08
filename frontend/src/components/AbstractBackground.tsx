"use client";

import React from "react";
import { motion as Motion } from "framer-motion";
import { useTheme } from "../contexts/ThemeContext";

export default function AbstractBackground() {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <div className="fixed inset-0 z-0 overflow-hidden pointer-events-none select-none isolation-auto transition-colors duration-700">
      {/* Top Right - Red/Pink (Light) or Slate (Dark) */}
      <Motion.div
        animate={{
          x: [0, 20, -20, 0],
          y: [0, -20, 20, 0],
          scale: [1, 1.1, 0.9, 1],
        }}
        transition={{
          duration: 15,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className={`absolute -top-[20%] -right-[10%] w-[60%] h-[60%] rounded-full blur-[140px] transition-colors duration-700 ${isDark ? 'bg-slate-500/10' : 'bg-[#EA4335]/[0.18]'}`}
      />

      {/* Bottom Left - Green/Teal (Light) or Grey (Dark) */}
      <Motion.div
        animate={{
          x: [0, -40, 40, 0],
          y: [0, 20, -20, 0],
          scale: [1, 1.1, 0.9, 1],
        }}
        transition={{
          duration: 22,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className={`absolute -bottom-[20%] -left-[10%] w-[65%] h-[65%] rounded-full blur-[150px] transition-colors duration-700 ${isDark ? 'bg-slate-400/5' : 'bg-[#34A853]/[0.12]'}`}
      />

      {/* Top Left - Blue (Light) or Slate (Dark) */}
      <Motion.div
        animate={{
          x: [0, 15, -15, 0],
          y: [0, 10, -10, 0],
          opacity: [0.35, 0.45, 0.35],
        }}
        transition={{
          duration: 14,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className={`absolute -top-[10%] -left-[5%] w-[50%] h-[50%] rounded-full blur-[130px] transition-colors duration-700 ${isDark ? 'bg-slate-600/10' : 'bg-[#4285F4]/[0.10]'}`}
      />

      {/* Middle Left - Yellow (Light) or Slate (Dark) */}
      <Motion.div
        animate={{
          x: [-20, 20, -20],
          y: [30, -30, 30],
          scale: [1, 1.1, 0.9, 1],
        }}
        transition={{
          duration: 19,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className={`absolute top-[30%] -left-[15%] w-[45%] h-[45%] rounded-full blur-[140px] transition-colors duration-700 ${isDark ? 'bg-slate-500/5' : 'bg-[#FBBC05]/[0.08]'}`}
      />

      {/* Center Top - Blue (Complementary) */}
      <Motion.div
        animate={{
          x: [-10, 10, -10],
          y: [10, -10, 10],
          opacity: [0.3, 0.4, 0.3],
        }}
        transition={{
          duration: 12,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className={`absolute top-[10%] left-[30%] w-[35%] h-[35%] rounded-full blur-[120px] transition-colors duration-700 ${isDark ? 'bg-slate-400/5' : 'bg-[#4285F4]/[0.08]'}`}
      />

      {/* Bottom Right - Yellow (Complementary) */}
      <Motion.div
        animate={{
          x: [20, -20, 20],
          y: [-10, 10, -10],
          scale: [1, 1.1, 1],
        }}
        transition={{
          duration: 20,
          repeat: Infinity,
          ease: "easeInOut",
        }}
        className={`absolute bottom-[10%] right-[5%] w-[40%] h-[40%] rounded-full blur-[130px] transition-colors duration-700 ${isDark ? 'bg-slate-600/5' : 'bg-[#FBBC05]/[0.08]'}`}
      />

      {/* Subtle Glow (Center) */}
      <div className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full blur-3xl opacity-50 transition-colors duration-700 ${isDark ? 'bg-gradient-to-tr from-slate-900/40 to-transparent' : 'bg-gradient-to-tr from-white/10 to-transparent'}`}></div>
    </div>
  );
}
