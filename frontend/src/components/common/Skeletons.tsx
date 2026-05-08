"use client";

import React from "react";

/**
 * Shared Skeleton components to ensure uniform "pulse" look across the CELTM platform.
 */

export function SkeletonPulse({ className }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-surface-container-low rounded-3xl ${className}`} />
  );
}

export function SectionSkeleton() {
  return (
    <div className="space-y-6">
      <SkeletonPulse className="h-48 w-full" />
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <SkeletonPulse className="h-32" />
        <SkeletonPulse className="h-32" />
        <SkeletonPulse className="h-32" />
        <SkeletonPulse className="h-32" />
      </div>
      <div className="grid gap-8 lg:grid-cols-2">
        <SkeletonPulse className="h-96" />
        <SkeletonPulse className="h-96" />
      </div>
    </div>
  );
}

export function StatCardSkeleton() {
  return <SkeletonPulse className="h-40 w-full" />;
}

export function DonutSkeleton() {
  return (
    <div className="flex flex-col items-center justify-center p-8">
      <div className="h-48 w-48 rounded-full border-[12px] border-surface-container animate-pulse" />
      <div className="mt-6 h-4 w-32 rounded-full bg-surface-container animate-pulse" />
    </div>
  );
}

export function ListSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonPulse key={i} className="h-20 w-full rounded-2xl" />
      ))}
    </div>
  );
}

export function FormSkeleton() {
  return (
    <div className="space-y-8">
      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-2">
          <SkeletonPulse className="h-4 w-24 rounded-full" />
          <SkeletonPulse className="h-12 w-full" />
        </div>
        <div className="space-y-2">
          <SkeletonPulse className="h-4 w-24 rounded-full" />
          <SkeletonPulse className="h-12 w-full" />
        </div>
      </div>
      <div className="space-y-2">
        <SkeletonPulse className="h-4 w-24 rounded-full" />
        <SkeletonPulse className="h-32 w-full" />
      </div>
    </div>
  );
}
