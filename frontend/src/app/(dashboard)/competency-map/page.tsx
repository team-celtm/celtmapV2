import React from 'react';

export default function Page() {
  return (
    <>
      

<section className="relative mb-16 overflow-hidden">
<div className="flex flex-col lg:flex-row items-end justify-between mb-10 gap-6">
<div className="max-w-2xl">
<span className="text-primary font-bold tracking-[0.3em] uppercase text-xs mb-4 block">Competency Intelligence</span>
<h1 className="text-5xl lg:text-7xl font-extrabold tracking-tighter leading-tight">Mastery <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-tertiary">Topology</span></h1>
<p className="mt-6 text-on-surface-variant text-lg max-w-lg leading-relaxed">
                        Visualizing the current organizational expertise landscape. High-resolution skill clustering derived from real-time performance and project output.
                    </p>
</div>
<div className="flex gap-4">
<div className="clay-card p-6 rounded-xl ">
<div className="text-primary text-4xl font-black mb-1">92%</div>
<div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Global Proficiency</div>
</div>
<div className="clay-card p-6 rounded-xl ">
<div className="text-secondary text-4xl font-black mb-1">14</div>
<div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Critical Gaps</div>
</div>
</div>
</div>

<div className="w-full h-[500px] clay-card rounded-xl relative overflow-hidden group">

<div className="absolute inset-0 opacity-40 mix-blend-screen pointer-events-none">
<div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/20 blur-[120px] rounded-full"></div>
<div className="absolute bottom-1/4 right-1/4 w-[500px] h-[500px] bg-secondary/10 blur-[150px] rounded-full"></div>
<div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] border border-outline-variant/10 dark:border-transparent rounded-full animate-pulse"></div>
<div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] border border-outline-variant/5 dark:border-transparent rounded-full"></div>
</div>

<div className="absolute top-20 left-[20%] z-10">
<div className="clay-card px-5 py-3 rounded-full border border-primary/40 flex items-center gap-3 cursor-pointer hover:scale-105 transition-transform">
<div className="w-2 h-2 rounded-full bg-primary shadow-[0_0_8px_#9fa7ff]"></div>
<span className="text-xs font-bold uppercase tracking-widest">Technical Domain</span>
</div>
<div className="mt-4 ml-8 space-y-2 opacity-60">
<div className="text-[10px] font-medium border-l border-primary/30 pl-3">CELTM Architecture</div>
<div className="text-[10px] font-medium border-l border-primary/30 pl-3">Cloud Synthesis</div>
</div>
</div>
<div className="absolute bottom-32 right-[25%] z-10">
<div className="clay-card px-5 py-3 rounded-full border border-secondary/40 flex items-center gap-3 cursor-pointer hover:scale-105 transition-transform">
<div className="w-2 h-2 rounded-full bg-secondary shadow-[0_0_8px_#c180ff]"></div>
<span className="text-xs font-bold uppercase tracking-widest">Leadership Vector</span>
</div>
</div>
<div className="absolute top-1/2 left-[55%] z-10">
<div className="clay-card px-5 py-3 rounded-full border border-tertiary/40 flex items-center gap-3 cursor-pointer hover:scale-105 transition-transform">
<div className="w-2 h-2 rounded-full bg-tertiary shadow-[0_0_8px_#c6fff3]"></div>
<span className="text-xs font-bold uppercase tracking-widest">Cognitive Soft Skills</span>
</div>
</div>

<div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/carbon-fibre.png')] opacity-5"></div>
<div className="absolute bottom-8 left-8 flex items-center gap-4 text-xs font-mono text-on-surface-variant/40">
<span>LAT: 42.3601</span>
<span>LNG: -71.0589</span>
<span className="animate-pulse">● LIVE STREAM</span>
</div>
</div>
</section>

<section className="mt-24">
<div className="flex items-center justify-between mb-12">
<div>
<h3 className="text-3xl font-bold tracking-tight">Competency Matrix</h3>
<p className="text-on-surface-variant text-sm mt-2">Quantitative assessment across key operational pillars.</p>
</div>
<div className="flex gap-2">
<button className="bg-surface-container-high px-5 py-2.5 rounded-full text-xs font-bold uppercase tracking-widest border border-outline-variant/10 dark:border-transparent hover:border-primary/50 transition-all">Export Report</button>
<button className="bg-primary text-on-primary px-5 py-2.5 rounded-full text-xs font-bold uppercase tracking-widest transition-all">Filter View</button>
</div>
</div>
<div className="overflow-x-auto no-scrollbar">
<table className="w-full text-left border-separate border-spacing-y-4">
<thead className="text-on-surface-variant text-[10px] uppercase tracking-[0.2em] font-bold">
<tr>
<th className="px-6 py-4">Competency Name</th>
<th className="px-6 py-4">Status</th>
<th className="px-6 py-4">Industry Benchmark</th>
<th className="px-6 py-4">Growth Trend</th>
<th className="px-6 py-4 text-right">Actions</th>
</tr>
</thead>
<tbody className="space-y-4">

<tr className="bg-surface-container-low/50 hover:bg-surface-container-low transition-colors group">
<td className="px-6 py-8 rounded-l-xl">
<div className="flex items-center gap-4">
<div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center text-primary">
<span className="material-symbols-outlined">psychology</span>
</div>
<div>
<div className="font-bold text-white tracking-tight">AI Strategy &amp; Ethics</div>
<div className="text-[10px] text-on-surface-variant font-medium">Cognitive Domain</div>
</div>
</div>
</td>
<td className="px-6 py-8">
<span className="bg-primary-container/20 text-primary-fixed text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-full border border-primary/20">Advanced</span>
</td>
<td className="px-6 py-8">
<div className="w-full max-w-[140px]">
<div className="flex justify-between text-[10px] mb-1 font-bold">
<span>78th Percentile</span>
<span className="text-primary">+4.2%</span>
</div>
<div className="h-1 clay-card rounded-full overflow-hidden">
<div className="h-full bg-primary w-[78%]"></div>
</div>
</div>
</td>
<td className="px-6 py-8">
<div className="flex items-center gap-2">
<svg className="w-24 h-8 glow-tail" fill="none" viewBox="0 0 100 30">
<path d="M0 25C10 25 15 5 25 10C35 15 45 28 55 20C65 12 75 2 100 5" stroke="#9fa7ff" strokeLinecap="round" strokeWidth="2" />
</svg>
</div>
</td>
<td className="px-6 py-8 rounded-r-xl text-right">
<button className="material-symbols-outlined text-on-surface-variant hover:text-white transition-colors">more_vert</button>
</td>
</tr>

<tr className="bg-surface-container-low/50 hover:bg-surface-container-low transition-colors group">
<td className="px-6 py-8 rounded-l-xl">
<div className="flex items-center gap-4">
<div className="w-10 h-10 bg-secondary/10 rounded-lg flex items-center justify-center text-secondary">
<span className="material-symbols-outlined">dynamic_feed</span>
</div>
<div>
<div className="font-bold text-white tracking-tight">System Architecture</div>
<div className="text-[10px] text-on-surface-variant font-medium">Technical Domain</div>
</div>
</div>
</td>
<td className="px-6 py-8">
<span className="bg-secondary-container/20 text-secondary-fixed text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-full border border-secondary/20">Intermediate</span>
</td>
<td className="px-6 py-8">
<div className="w-full max-w-[140px]">
<div className="flex justify-between text-[10px] mb-1 font-bold">
<span>62nd Percentile</span>
<span className="text-secondary">+1.8%</span>
</div>
<div className="h-1 clay-card rounded-full overflow-hidden">
<div className="h-full bg-secondary w-[62%]"></div>
</div>
</div>
</td>
<td className="px-6 py-8">
<div className="flex items-center gap-2">
<svg className="w-24 h-8 glow-tail" fill="none" viewBox="0 0 100 30">
<path d="M0 20C20 22 40 18 60 12C80 6 100 8" stroke="#c180ff" strokeLinecap="round" strokeWidth="2" />
</svg>
</div>
</td>
<td className="px-6 py-8 rounded-r-xl text-right">
<button className="material-symbols-outlined text-on-surface-variant hover:text-white transition-colors">more_vert</button>
</td>
</tr>

<tr className="bg-surface-container-low/50 hover:bg-surface-container-low transition-colors group">
<td className="px-6 py-8 rounded-l-xl">
<div className="flex items-center gap-4">
<div className="w-10 h-10 bg-tertiary/10 rounded-lg flex items-center justify-center text-tertiary">
<span className="material-symbols-outlined">groups</span>
</div>
<div>
<div className="font-bold text-white tracking-tight">Cross-Functional Synergy</div>
<div className="text-[10px] text-on-surface-variant font-medium">Soft Skills</div>
</div>
</div>
</td>
<td className="px-6 py-8">
<span className="bg-tertiary-container/10 text-tertiary-dim text-[10px] font-black uppercase tracking-widest px-3 py-1 rounded-full border border-tertiary/20">Advanced</span>
</td>
<td className="px-6 py-8">
<div className="w-full max-w-[140px]">
<div className="flex justify-between text-[10px] mb-1 font-bold">
<span>89th Percentile</span>
<span className="text-tertiary">+12.4%</span>
</div>
<div className="h-1 clay-card rounded-full overflow-hidden">
<div className="h-full bg-tertiary w-[89%]"></div>
</div>
</div>
</td>
<td className="px-6 py-8">
<div className="flex items-center gap-2">
<svg className="w-24 h-8 glow-tail" fill="none" viewBox="0 0 100 30">
<path d="M0 28L20 20L40 25L60 10L80 15L100 2" stroke="#c6fff3" strokeLinecap="round" strokeWidth="2" />
</svg>
</div>
</td>
<td className="px-6 py-8 rounded-r-xl text-right">
<button className="material-symbols-outlined text-on-surface-variant hover:text-white transition-colors">more_vert</button>
</td>
</tr>
</tbody>
</table>
</div>
</section>

<section className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-8">
<div className="md:col-span-2 clay-card p-10 rounded-xl relative overflow-hidden group">
<div className="relative z-10">
<h4 className="text-2xl font-bold mb-4">Strategic Recommendation</h4>
<p className="text-on-surface-variant leading-relaxed max-w-xl">
                        Based on current topography data, there is a cluster weakness in <span className="text-primary font-bold">Quantum Readiness</span>. We recommend initiating a cross-domain sprint to mitigate the 14 identified gaps within the Q3 technical roadmap.
                    </p>
<button className="mt-8 flex items-center gap-3 text-primary text-xs font-bold uppercase tracking-widest group-hover:gap-5 transition-all">
                        View Training Modules <span className="material-symbols-outlined">arrow_forward</span>
</button>
</div>
<div className="absolute -right-20 -bottom-20 w-64 h-64 bg-primary/10 blur-[80px] rounded-full group-hover:scale-125 transition-transform duration-700"></div>
</div>
<div className="bg-surface-container-high p-10 rounded-xl flex flex-col justify-between border border-outline-variant/10 dark:border-transparent">
<div>
<span className="material-symbols-outlined text-secondary text-4xl mb-6">bolt</span>
<h4 className="text-xl font-bold mb-2">Peak Velocity</h4>
<p className="text-sm text-on-surface-variant">Fastest growing domain in your ecosystem.</p>
</div>
<div className="mt-8">
<div className="text-secondary text-5xl font-black">+42%</div>
<div className="text-[10px] font-bold text-on-surface-variant uppercase tracking-widest mt-2">Cloud Synthesis Mastery</div>
</div>
</div>
</section>

    </>
  );
}
