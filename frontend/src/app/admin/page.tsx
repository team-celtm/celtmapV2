"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import AppIcon from "@/components/AppIcon";

export default function AdminDashboard() {
  const router = useRouter();
  
  // Auth States
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [showSecretModal, setShowSecretModal] = useState(false);
  const [secretCode, setSecretCode] = useState("");
  
  // Toast State
  const [toast, setToast] = useState<{ title: string; description: string; variant?: string } | null>(null);
  
  // Ingestion States
  const [file, setFile] = useState<File | null>(null);
  const [roleName, setRoleName] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  useEffect(() => {
    const token = localStorage.getItem("adminToken");
    const verified = localStorage.getItem("adminVerified");
    
    if (!token) {
      router.push("/login");
      return;
    }

    if (verified !== "true") {
      setShowSecretModal(true);
    } else {
      setIsAuthenticated(true);
    }
  }, [router]);

  const showNotification = (title: string, description: string, variant?: string) => {
    setToast({ title, description, variant });
  };

  const handleLogout = () => {
    localStorage.removeItem("adminToken");
    localStorage.removeItem("adminVerified");
    router.push("/login");
  };

  const handleVerifySecret = (e: React.FormEvent) => {
    e.preventDefault();
    if (secretCode === "CELTM2026") {
      localStorage.setItem("adminVerified", "true");
      setShowSecretModal(false);
      setIsAuthenticated(true);
      showNotification("Access Granted", "Welcome to the Secure Admin Control Center.");
    } else {
      showNotification("Access Denied", "Invalid secure gateway code.", "destructive");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    if (roleName) {
      formData.append("role_name", roleName);
    }

    try {
      const token = localStorage.getItem("adminToken");
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/ingest-csv${roleName ? `?role_name=${encodeURIComponent(roleName)}` : ''}`, {
        method: "POST",
        body: formData,
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      
      if (!res.ok) {
        if (res.status === 401) {
            handleLogout();
            return;
        }
        throw new Error("Ingestion failed");
      }
      
      const data = await res.json();
      setStats(data.stats);
      setFile(null);
      showNotification("Ingestion Successful", `Processed ${data.stats.total_rows} rows successfully.`);
    } catch (error) {
      showNotification("Ingestion Error", "Failed to process the question bank.", "destructive");
    } finally {
      setIsUploading(false);
    }
  };

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const token = localStorage.getItem("adminToken");
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/sync-celtmind`, { 
        method: "POST",
        headers: {
            "Authorization": `Bearer ${token}`
        }
      });
      if (!res.ok) throw new Error("Sync failed");

      showNotification("Sync Initiated", "Subject synchronization is running in the background.");
    } catch (error) {
      showNotification("Sync Failure", "Unable to trigger synchronizer.", "destructive");
    } finally {
      setIsSyncing(false);
    }
  };

  if (!isAuthenticated && !showSecretModal) return null;

  return (
    <div className="min-h-screen bg-[#F8FAFC] dark:bg-[#0F172A] p-6 lg:p-10 font-sans transition-colors duration-500">
      
      {/* Toast Notification */}
      <AnimatePresence>
        {toast && (
          <motion.div 
            initial={{ opacity: 0, y: -50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -50 }}
            className={`fixed top-10 right-10 z-[300] p-6 rounded-[24px] shadow-2xl backdrop-blur-xl border ${
              toast.variant === "destructive" 
                ? "bg-red-500/10 border-red-500/20 text-red-500" 
                : "bg-emerald-500/10 border-emerald-500/20 text-emerald-600"
            }`}
          >
            <p className="font-black uppercase tracking-widest text-[10px] mb-1">{toast.title}</p>
            <p className="text-sm font-bold opacity-80">{toast.description}</p>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="max-w-[1400px] mx-auto space-y-8">
        
        {/* Header Section */}
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex items-center gap-5">
            <div className="h-16 w-16 flex items-center justify-center rounded-[24px] bg-indigo-500/10 text-indigo-500">
              <AppIcon name="verified" className="h-10 w-10" />
            </div>
            <div>
              <h1 className="text-3xl font-black tracking-tight text-slate-900 dark:text-white uppercase italic">Secure Admin</h1>
              <div className="flex items-center gap-2 mt-1">
                <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <p className="text-xs font-bold text-slate-500 uppercase tracking-widest">Nexus System Isolated</p>
              </div>
            </div>
          </div>
          <button 
            onClick={handleLogout}
            className="rounded-full bg-slate-200/50 dark:bg-white/5 text-slate-600 dark:text-slate-400 hover:bg-red-500/10 hover:text-red-500 px-6 py-4 flex items-center transition-all"
          >
            <AppIcon name="logout" className="h-5 w-5 mr-2" />
            <span className="font-bold uppercase tracking-widest text-[10px]">Terminate Session</span>
          </button>
        </header>

        <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
          
          {/* Main Controls - 8 Columns */}
          <div className="xl:col-span-8 space-y-8">
            
            {/* Ingestion Console */}
            <section className="bg-white dark:bg-[#1E293B] rounded-[40px] p-8 shadow-xl shadow-slate-200/50 dark:shadow-none border border-slate-100 dark:border-white/5">
              <div className="flex items-center justify-between mb-8">
                <div className="flex items-center gap-3">
                  <AppIcon name="query_stats" className="h-6 w-6 text-indigo-500" />
                  <h2 className="text-xl font-black uppercase tracking-tight">Question Bank Ingestion</h2>
                </div>
                <div className="rounded-full bg-slate-100 dark:bg-white/5 px-4 py-1.5 text-[10px] font-bold text-slate-500 uppercase">CSV Module v2.0</div>
              </div>

              <div className="grid md:grid-cols-2 gap-8">
                <div className="space-y-6">
                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400">Target Role</label>
                    <input 
                      type="text"
                      placeholder="e.g. Data Scientist"
                      value={roleName}
                      onChange={(e) => setRoleName(e.target.value)}
                      className="w-full rounded-2xl border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 px-5 py-4 text-sm text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500/40 transition-all font-medium"
                    />
                  </div>

                  <div className="relative group overflow-hidden rounded-[32px] border-2 border-dashed border-slate-200 dark:border-white/10 p-10 flex flex-col items-center justify-center transition-all hover:border-indigo-500/50 hover:bg-indigo-500/5">
                    <input 
                      type="file" 
                      accept=".csv"
                      onChange={handleFileChange}
                      className="absolute inset-0 z-10 cursor-pointer opacity-0"
                    />
                    <div className="h-16 w-16 bg-slate-100 dark:bg-white/10 rounded-full flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                      <AppIcon name="bolt" className="h-8 w-8 text-slate-400 group-hover:text-indigo-500" />
                    </div>
                    <p className="text-sm font-bold text-slate-700 dark:text-slate-200">
                      {file ? file.name : "Select Spreadsheet"}
                    </p>
                    <p className="text-[10px] text-slate-400 mt-2 uppercase tracking-widest font-black">CSV Question Bank only</p>
                  </div>

                  <button 
                    className="w-full rounded-2xl h-14 bg-indigo-600 text-white font-black uppercase tracking-[0.2em] text-xs shadow-lg shadow-indigo-500/25 hover:scale-[1.01] active:scale-[0.99] transition-all disabled:opacity-50"
                    onClick={handleUpload}
                    disabled={isUploading || !file}
                  >
                    {isUploading ? "Uploading Data..." : "Execute Ingestion"}
                  </button>
                </div>

                {/* Schema Definition Card */}
                <div className="bg-[#F1F5F9] dark:bg-[#0F172A]/50 rounded-[32px] p-6 border border-slate-200 dark:border-white/5">
                   <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <AppIcon name="article" className="h-5 w-5 text-indigo-500" />
                        <h3 className="text-xs font-black uppercase tracking-widest">Master CSV Schema</h3>
                      </div>
                   </div>
                   <div className="space-y-4 overflow-y-auto max-h-[340px] pr-2 custom-scrollbar">
                      <div className="text-[10px] space-y-2">
                        {[
                          { col: "subject", desc: "Top-level category (e.g. Artificial Intelligence)" },
                          { col: "topic", desc: "Specific technical skill or sub-domain" },
                          { col: "difficulty", desc: "Must be exactly: Easy, Medium, or Hard" },
                          { col: "question_text", desc: "The clear, grammatically correct question body" },
                          { col: "option_a", desc: "First possible choice (Text only)" },
                          { col: "option_b", desc: "Second possible choice (Text only)" },
                          { col: "option_c", desc: "Third possible choice (Text only)" },
                          { col: "option_d", desc: "Fourth possible choice (Text only)" },
                          { col: "correct_answer", desc: "MUST perfectly match the text of choice a, b, c, or d" },
                          { col: "explanation", desc: "Detailed reasoning for the correct choice" }
                        ].map((item, i) => (
                          <div key={i} className="flex items-start justify-between py-2.5 border-b border-slate-200 dark:border-white/5 last:border-0">
                            <span className="font-mono text-indigo-500 font-bold shrink-0">{item.col}</span>
                            <span className="text-slate-500 text-right ml-4">{item.desc}</span>
                          </div>
                        ))}
                      </div>
                      <div className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-2xl space-y-2">
                        <p className="text-[10px] font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-tighter">Pro-Tip for Operators:</p>
                        <p className="text-[10px] leading-relaxed text-indigo-500 italic">
                          Encoding: UTF-8 (Strict). Headers are case-insensitive. Row limit per ingest: 500 records.
                        </p>
                      </div>
                   </div>
                </div>
              </div>

              {stats && (
                <motion.div 
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-8 grid grid-cols-2 lg:grid-cols-4 gap-4"
                >
                  {[
                    { label: "Lines Processed", val: stats.total_rows, color: "bg-blue-500" },
                    { label: "Questions Sync", val: stats.questions_added, color: "bg-emerald-500" },
                    { label: "Subjects Created", val: stats.subjects_created, color: "bg-amber-500" },
                    { label: "Errors Found", val: stats.errors.length, color: "bg-red-500" }
                  ].map((s, i) => (
                    <div key={i} className="bg-slate-50 dark:bg-white/5 p-5 rounded-3xl border border-slate-100 dark:border-white/5">
                        <div className={`h-1.5 w-8 ${s.color} rounded-full mb-3`} />
                        <p className="text-2xl font-black text-slate-900 dark:text-white">{s.val}</p>
                        <p className="text-[9px] font-bold uppercase tracking-widest text-slate-400 mt-1">{s.label}</p>
                    </div>
                  ))}
                </motion.div>
              )}
            </section>
          </div>

          {/* Sidebar - 4 Columns */}
          <div className="xl:col-span-4 space-y-8">
            
            {/* System Sync */}
            <section className="bg-white dark:bg-[#1E293B] rounded-[40px] p-8 shadow-xl shadow-slate-200/50 dark:shadow-none border border-slate-100 dark:border-white/5">
              <div className="flex items-center gap-3 mb-6">
                <AppIcon name="history" className="h-6 w-6 text-indigo-500" />
                <h2 className="text-xl font-black uppercase tracking-tight">CeltMind Sync</h2>
              </div>
              <p className="text-sm text-slate-500 leading-relaxed mb-8">
                Force trigger a global repository update. This will recalibrate role requirements and subject hierarchies across all clusters.
              </p>
              <button 
                className="w-full rounded-2xl h-14 border-2 border-slate-100 dark:border-white/10 hover:bg-slate-50 dark:hover:bg-white/5 text-sm font-bold uppercase tracking-widest transition-all disabled:opacity-50"
                onClick={handleSync}
                disabled={isSyncing}
              >
                {isSyncing ? "Syncing Clusters..." : "Full System Synchronize"}
              </button>
              
              <div className="mt-6 flex items-start gap-3 p-4 rounded-2xl bg-amber-500/5 border border-amber-500/10">
                <AppIcon name="warning" className="h-5 w-5 text-amber-500 mt-0.5" />
                <p className="text-[11px] text-amber-600/80 font-medium leading-relaxed">
                  Resource intensive. Do not trigger more than once per hour.
                </p>
              </div>
            </section>

            {/* Audit Logs */}
            <section className="bg-white dark:bg-[#1E293B] rounded-[40px] p-8 shadow-xl shadow-slate-200/50 dark:shadow-none border border-slate-100 dark:border-white/5">
              <div className="flex items-center justify-between mb-6">
                 <h2 className="text-sm font-black uppercase tracking-widest">Security Audit</h2>
                 <span className="h-2 w-2 rounded-full bg-emerald-500" />
              </div>
              <div className="space-y-4">
                {[
                  { icon: "verified", msg: "Double-Auth Verified", time: "Just now", color: "text-emerald-400" },
                  { icon: "lock", msg: "Isolated Domain Locked", time: "5m ago", color: "text-blue-400" },
                  { icon: "farsight_digital", msg: "RBAC Token Issued", time: "22m ago", color: "text-indigo-400" }
                ].map((log, i) => (
                  <div key={i} className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-3">
                      <AppIcon name={log.icon} className={`h-4 w-4 ${log.color}`} />
                      <span className="text-[11px] font-bold text-slate-600 dark:text-slate-400">{log.msg}</span>
                    </div>
                    <span className="text-[9px] text-slate-400 uppercase">{log.time}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      </div>

      {/* Secondary Secret Verification Modal */}
      <AnimatePresence>
        {showSecretModal && (
          <div className="fixed inset-0 z-[200] flex items-center justify-center p-4">
            <motion.div 
               initial={{ opacity: 0 }}
               animate={{ opacity: 1 }}
               exit={{ opacity: 0 }}
               className="absolute inset-0 bg-[#0F172A]/90 backdrop-blur-md" 
            />
            <motion.div
              initial={{ scale: 0.9, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.9, opacity: 0, y: 20 }}
              className="relative w-full max-w-md rounded-[48px] bg-white dark:bg-[#1E293B] p-10 shadow-2xl text-center"
            >
              <div className="mx-auto mb-8 h-20 w-20 flex items-center justify-center rounded-[32px] bg-amber-500/10 text-amber-500">
                <AppIcon name="lock" className="h-10 w-10" />
              </div>
              <h3 className="text-2xl font-black text-slate-900 dark:text-white uppercase tracking-tight">Security Gateway</h3>
              <p className="mt-2 text-slate-500 dark:text-slate-400 font-medium">Enter your administrative authorization code to unlock the control center.</p>
              
              <form onSubmit={handleVerifySecret} className="mt-10 space-y-6">
                <input 
                  type="password"
                  required
                  placeholder="••••••••"
                  autoFocus
                  value={secretCode}
                  onChange={(e) => setSecretCode(e.target.value)}
                  className="w-full rounded-3xl border-2 border-slate-100 dark:border-white/5 bg-slate-50 dark:bg-white/5 px-6 py-5 text-center text-3xl font-black tracking-[0.5em] text-slate-900 dark:text-white focus:outline-none focus:border-amber-500/50 transition-all"
                />
                <button 
                  type="submit"
                  className="w-full rounded-2xl h-16 bg-amber-500 hover:bg-amber-600 text-black font-black uppercase tracking-[0.3em] text-xs shadow-xl shadow-amber-500/20 transition-all hover:scale-[1.02]"
                >
                  Verify Access
                </button>
                <button 
                  type="button"
                  onClick={handleLogout}
                  className="text-[10px] font-black uppercase tracking-[0.2em] text-slate-400 hover:text-red-500 transition-colors"
                >
                  Abort Operation
                </button>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
