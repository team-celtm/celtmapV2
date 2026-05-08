"use client";

import React from 'react';
import { motion as Motion, useReducedMotion } from 'framer-motion';
import { useTheme } from '../../contexts/ThemeContext';
import AppIcon from '../AppIcon';
import FlowingPattern from './FlowingPattern';

interface AmbientGlow {
  className: string;
  lightClassName: string;
  darkClassName: string;
  animate: any;
  duration: number;
}

const ambientGlows: AmbientGlow[] = [
  {
    className: 'left-[-10rem] top-[-8rem] h-[24rem] w-[24rem]',
    lightClassName: 'bg-[radial-gradient(circle,rgba(66,133,244,0.18)_0%,rgba(66,133,244,0)_68%)]',
    darkClassName: 'bg-[radial-gradient(circle,rgba(66,133,244,0.12)_0%,rgba(66,133,244,0)_72%)]',
    animate: { x: [0, 24, -12, 0], y: [0, 18, -10, 0], scale: [1, 1.05, 0.98, 1] },
    duration: 18,
  },
  {
    className: 'right-[-7rem] top-[10%] h-[22rem] w-[22rem]',
    lightClassName: 'bg-[radial-gradient(circle,rgba(52,168,83,0.16)_0%,rgba(52,168,83,0)_70%)]',
    darkClassName: 'bg-[radial-gradient(circle,rgba(52,168,83,0.1)_0%,rgba(52,168,83,0)_72%)]',
    animate: { x: [0, -22, 10, 0], y: [0, 16, -8, 0], scale: [1, 1.04, 0.97, 1] },
    duration: 20,
  },
  {
    className: 'left-[12%] bottom-[-8rem] h-[20rem] w-[20rem]',
    lightClassName: 'bg-[radial-gradient(circle,rgba(234,67,53,0.16)_0%,rgba(234,67,53,0)_72%)]',
    darkClassName: 'bg-[radial-gradient(circle,rgba(234,67,53,0.1)_0%,rgba(234,67,53,0)_74%)]',
    animate: { x: [0, 18, -10, 0], y: [0, -16, 8, 0], scale: [1, 1.03, 0.99, 1] },
    duration: 22,
  },
  {
    className: 'right-[22%] bottom-[6%] h-[16rem] w-[16rem]',
    lightClassName: 'bg-[radial-gradient(circle,rgba(251,188,5,0.18)_0%,rgba(251,188,5,0)_68%)]',
    darkClassName: 'bg-[radial-gradient(circle,rgba(251,188,5,0.12)_0%,rgba(251,188,5,0)_72%)]',
    animate: { x: [0, -12, 8, 0], y: [0, 12, -6, 0], scale: [1, 1.05, 0.98, 1] },
    duration: 17,
  },
];

interface Floating3DObjectProps {
  type: 'sphere' | 'ring' | 'prism';
  className: string;
  delay: number;
  duration: number;
}

const Floating3DObject = ({ type, className, delay, duration }: Floating3DObjectProps) => (
  <Motion.div
    initial={{ opacity: 0, scale: 0.5, rotate: 0 }}
    animate={{ 
      opacity: [0.3, 0.6, 0.3], 
      scale: [0.9, 1.1, 0.9],
      rotate: [0, 360],
      y: [0, -40, 0],
      x: [0, 20, 0]
    }}
    transition={{ 
      duration, 
      delay, 
      repeat: Infinity, 
      ease: "easeInOut" 
    }}
    className={`absolute pointer-events-none drop-shadow-2xl ${className}`}
  >
    {type === 'sphere' && (
      <svg viewBox="0 0 100 100" className="w-full h-full opacity-40">
        <defs>
          <radialGradient id="sphereGrad" cx="30%" cy="30%" r="70%">
            <stop offset="0%" stopColor="rgba(255,255,255,0.4)" />
            <stop offset="50%" stopColor="rgba(66,133,244,0.15)" />
            <stop offset="100%" stopColor="rgba(0,0,0,0)" />
          </radialGradient>
        </defs>
        <circle cx="50" cy="50" r="45" fill="url(#sphereGrad)" />
        <circle cx="50" cy="50" r="45" fill="none" stroke="rgba(255,255,255,0.1)" strokeWidth="0.5" />
      </svg>
    )}
    {type === 'ring' && (
      <svg viewBox="0 0 100 100" className="w-full h-full opacity-30">
        <ellipse cx="50" cy="50" rx="45" ry="20" fill="none" stroke="rgba(255,255,255,0.15)" strokeWidth="3" transform="rotate(-30 50 50)" />
        <ellipse cx="50" cy="50" rx="45" ry="20" fill="none" stroke="rgba(66,133,244,0.2)" strokeWidth="1" transform="rotate(-30 50 50)" />
      </svg>
    )}
    {type === 'prism' && (
      <svg viewBox="0 0 100 100" className="w-full h-full opacity-25">
        <path d="M50 10 L90 80 L10 80 Z" fill="rgba(255,255,255,0.08)" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />
        <path d="M50 10 L50 80" stroke="rgba(255,255,255,0.1)" strokeWidth="0.5" />
      </svg>
    )}
  </Motion.div>
);

const objects3D = [
  { type: 'sphere', className: 'left-[10%] top-[15%] w-32 h-32', delay: 0, duration: 15 },
  { type: 'ring', className: 'right-[15%] top-[25%] w-48 h-48', delay: 2, duration: 20 },
  { type: 'sphere', className: 'right-[5%] bottom-[20%] w-24 h-24', delay: 1, duration: 18 },
  { type: 'prism', className: 'left-[20%] bottom-[15%] w-20 h-20', delay: 3, duration: 22 },
  { type: 'ring', className: 'left-[40%] top-[10%] w-16 h-16', delay: 5, duration: 14 },
  { type: 'sphere', className: 'right-[30%] bottom-[40%] w-12 h-12', delay: 4, duration: 16 },
] as const;

export default function AuthBackdrop({ children }: { children: React.ReactNode }) {
  const { isDarkMode } = useTheme();
  const reduceMotion = useReducedMotion();

  // Force light aesthetic for Auth pages regardless of global theme state if requested, 
  // but usually we can just use the provided colors.
  
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#fafafa] transition-colors duration-300">
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,#ffffff_0%,#fafafa_45%,#f5f5f5_100%)]" />
        
        <FlowingPattern isDarkMode={false} />
        
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(66,133,244,0.03)_0%,rgba(66,133,244,0)_34%),radial-gradient(circle_at_80%_18%,rgba(52,168,83,0.02)_0%,rgba(52,168,83,0)_24%)] opacity-100" />

        {ambientGlows.map((glow) => (
          <Motion.div
            key={glow.className}
            className={`absolute rounded-full blur-3xl ${glow.className} ${glow.lightClassName}`}
            animate={reduceMotion ? undefined : glow.animate}
            transition={
              reduceMotion
                ? undefined
                : {
                    duration: glow.duration,
                    repeat: Number.POSITIVE_INFINITY,
                    repeatType: 'mirror',
                    ease: 'easeInOut',
                  }
            }
            style={{ willChange: 'transform, opacity' }}
          />
        ))}

        {objects3D.map((obj, i) => (
          <Floating3DObject 
            key={i}
            type={obj.type}
            className={obj.className}
            delay={obj.delay}
            duration={obj.duration}
          />
        ))}
      </div>

      {children}
    </div>
  );
}
