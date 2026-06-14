"use client";

import React from 'react';
import Link from 'next/link';
import { motion as Motion } from 'framer-motion';
import AppIcon from "@/components/AppIcon";

export default function InterviewConsoleComingSoon() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh] p-8 text-center animate-fade-in">
      <Motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="clay-card rounded-[32px] p-10 max-w-2xl w-full"
      >
        <div className="mx-auto w-24 h-24 bg-primary/10 rounded-full flex items-center justify-center mb-6">
          <AppIcon name="mic" className="h-12 w-12 text-primary" />
        </div>
        
        <h1 className="text-4xl font-extrabold text-on-surface mb-4">
          Interview Console
        </h1>
        
        <div className="inline-block bg-gradient-to-r from-primary to-secondary text-white px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-widest mb-6">
          Coming Soon
        </div>
        
        <p className="text-lg text-on-surface-variant mb-8 leading-relaxed max-w-lg mx-auto">
          We&apos;re building a next-generation AI-powered interview experience. 
          Soon you&apos;ll be able to practice with our intelligent avatars, receive real-time feedback, 
          and track your performance progression.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10 text-left">
          <div className="bg-surface-container-low rounded-2xl p-4 border border-outline-variant/10">
            <AppIcon name="smart_toy" className="mb-2 h-5 w-5 text-primary" />
            <h3 className="font-bold text-sm text-on-surface">AI Avatars</h3>
            <p className="text-xs text-on-surface-variant mt-1">Practice with diverse personas</p>
          </div>
          <div className="bg-surface-container-low rounded-2xl p-4 border border-outline-variant/10">
            <AppIcon name="analytics" className="mb-2 h-5 w-5 text-primary" />
            <h3 className="font-bold text-sm text-on-surface">Real-time Stats</h3>
            <p className="text-xs text-on-surface-variant mt-1">Get immediate feedback</p>
          </div>
          <div className="bg-surface-container-low rounded-2xl p-4 border border-outline-variant/10">
            <AppIcon name="history" className="mb-2 h-5 w-5 text-primary" />
            <h3 className="font-bold text-sm text-on-surface">Review Sessions</h3>
            <p className="text-xs text-on-surface-variant mt-1">Watch and learn from past</p>
          </div>
        </div>
        
        <Link 
          href="/dashboard?refresh=1"
          className="inline-flex items-center gap-2 rounded-full bg-surface-container-high px-6 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-on-surface hover:bg-surface-container-highest transition-colors"
        >
          <AppIcon name="arrow_back" className="h-4 w-4" />
          Back to Dashboard
        </Link>
      </Motion.div>
    </div>
  );
}
