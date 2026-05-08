"use client";

import React from 'react';
import Link from 'next/link';
import { motion as Motion } from 'framer-motion';

export default function SessionsComingSoon() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] p-8 text-center animate-fade-in">
      <Motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="clay-card rounded-[32px] p-10 max-w-2xl w-full"
      >
        <div className="mx-auto w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center mb-6">
          <span className="material-symbols-outlined text-5xl text-primary">video_call</span>
        </div>
        
        <h1 className="text-4xl font-extrabold text-on-surface mb-4">
          Live Sessions
        </h1>
        
        <div className="inline-block bg-gradient-to-r from-primary to-secondary text-white px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-widest mb-6">
          Coming Soon
        </div>
        
        <p className="text-lg text-on-surface-variant mb-8 leading-relaxed max-w-lg mx-auto">
          We&apos;re preparing a seamless platform for all your live coaching, mock interviews, and mentoring sessions.
          Expect integrated video calls, collaborative whiteboards, and instant recording access directly within CELTM.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10 text-left">
          <div className="bg-surface-container-low rounded-2xl p-4 border border-outline-variant/10">
            <span className="material-symbols-outlined text-primary mb-2">group</span>
            <h3 className="font-bold text-sm text-on-surface">1-on-1 Coaching</h3>
            <p className="text-xs text-on-surface-variant mt-1">Direct access to experts</p>
          </div>
          <div className="bg-surface-container-low rounded-2xl p-4 border border-outline-variant/10">
            <span className="material-symbols-outlined text-primary mb-2">event_available</span>
            <h3 className="font-bold text-sm text-on-surface">Easy Scheduling</h3>
            <p className="text-xs text-on-surface-variant mt-1">Book slots in seconds</p>
          </div>
          <div className="bg-surface-container-low rounded-2xl p-4 border border-outline-variant/10">
            <span className="material-symbols-outlined text-primary mb-2">movie</span>
            <h3 className="font-bold text-sm text-on-surface">Cloud Recordings</h3>
            <p className="text-xs text-on-surface-variant mt-1">Revisit previous sessions</p>
          </div>
        </div>
        
        <Link 
          href="/dashboard?refresh=1"
          className="inline-flex items-center gap-2 rounded-full bg-surface-container-high px-6 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-on-surface hover:bg-surface-container-highest transition-colors"
        >
          <span className="material-symbols-outlined text-lg">arrow_back</span>
          Back to Dashboard
        </Link>
      </Motion.div>
    </div>
  );
}
