"use client";

import Link from "next/link";
import { type KeyboardEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";

import AuthBackdrop from "@/components/auth/AuthBackdrop";
import CeltmLogo from "@/components/CeltmLogo";
import { useAuth } from "@/contexts/AuthContext";
import { ApiError, apiFetch } from "@/lib/api";
import type {
  ProfileRead,
  UserPreferenceRead,
} from "@/lib/celtm";

interface OnboardingMetadata {
  bio?: string;
  location?: string;
  target_industry?: string;
}

type OnboardingTabId = "identity" | "direction" | "background";

interface OnboardingTabDefinition {
  id: OnboardingTabId;
  label: string;
  title: string;
  description: string;
}

const onboardingTabs: OnboardingTabDefinition[] = [
  {
    id: "identity",
    label: "Identity",
    title: "Start with the profile basics.",
    description: "Use the same identity details that should appear across CELTM.",
  },
  {
    id: "direction",
    label: "Direction",
    title: "Define the role CELTM should optimize for.",
    description: "These answers shape the dashboard, weekly plan, and assessment focus.",
  },
  {
    id: "background",
    label: "Background",
    title: "Add the context behind your learning path.",
    description: "Your skills and bio help CELTM tailor recommendations more accurately.",
  },
];

// India Specific Location Data
const INDIA_LOCATIONS = {
  "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Nashik", "Thane", "Aurangabad", "Solapur"],
  "Karnataka": ["Bengaluru", "Mysuru", "Hubballi-Dharwad", "Mangaluru", "Belagavi", "Vijayapura"],
  "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Tiruchirappalli", "Salem", "Tirunelveli"],
  "Delhi": ["New Delhi", "North Delhi", "South Delhi", "West Delhi", "East Delhi"],
  "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Khammam", "Karimnagar"],
  "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar"],
  "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Asansol", "Siliguri"],
  "Rajasthan": ["Jaipur", "Jodhpur", "Kota", "Bikaner", "Ajmer", "Udaipur"],
  "Uttar Pradesh": ["Lucknow", "Kanpur", "Ghaziabad", "Agra", "Meerut", "Varanasi"],
  "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda"],
  "Haryana": ["Gurugram", "Faridabad", "Panipat", "Ambala", "Karnal", "Rohtak"],
  "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Malappuram"],
  "Madhya Pradesh": ["Indore", "Bhopal", "Jabalpur", "Gwalior", "Ujjain"],
  "Bihar": ["Patna", "Gaya", "Bhagalpur", "Muzaffarpur", "Purnia"],
  "Assam": ["Guwahati", "Dibrugarh", "Silchar", "Jorhat", "Nagaon"],
};

const COUNTRIES = [
  "India",
  "United States",
  "United Kingdom",
  "Canada",
  "Australia",
  "Germany",
  "Singapore",
  "Remote",
];

function parseSkills(value: string): string[] {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

export default function OnboardingPage() {
  const router = useRouter();
  const { user, isLoading, refreshProfile } = useAuth();
  const [isSaving, setIsSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [certificateFiles, setCertificateFiles] = useState<File[]>([]);
  const [activeTab, setActiveTab] = useState<OnboardingTabId>("identity");
  const [form, setForm] = useState({
    fullName: undefined as string | undefined,
    currentRole: undefined as string | undefined,
    focusRole: undefined as string | undefined,
    weeklyGoal: undefined as string | undefined,
    location: undefined as string | undefined, // Legacy fallback
    country: "India" as string,
    state: "" as string,
    city: "" as string,
    targetIndustry: undefined as string | undefined,
    bio: undefined as string | undefined,
    skills: undefined as string | undefined,
  });

  useEffect(() => {
    if (isLoading) {
      return;
    }

    if (!user) {
      router.replace("/login");
      return;
    }

    if (user.hasCompletedOnboarding && !isSaving) {
      if (!user.hasCompletedPlacement) {
        router.replace("/assessment");
      } else {
        router.replace("/dashboard");
      }
    }
  }, [isLoading, router, user, isSaving]);

  const activeTabIndex = onboardingTabs.findIndex((tab) => tab.id === activeTab);
  const activeTabDefinition = onboardingTabs[activeTabIndex] ?? onboardingTabs[0];
  const isLastTab = activeTabIndex === onboardingTabs.length - 1;

  const heading = user?.name ? `Welcome, ${user.name.split(" ")[0]}` : "Set up your workspace";

  const handleChange = (field: keyof typeof form, value: string) => {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const getFormValue = (field: keyof typeof form, fallback = "") => form[field] ?? fallback;

  const moveToTab = (tabId: OnboardingTabId) => {
    setActiveTab(tabId);
    setError(null);
  };

  const moveTabByOffset = (offset: -1 | 1) => {
    const nextIndex = activeTabIndex + offset;
    if (nextIndex < 0 || nextIndex >= onboardingTabs.length) {
      return;
    }

    moveToTab(onboardingTabs[nextIndex].id);
  };

  const handleTabKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    tabIndex: number,
  ) => {
    const focusTab = (nextIndex: number) => {
      const tabs = event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>(
        '[role="tab"]',
      );
      tabs?.[nextIndex]?.focus();
      moveToTab(onboardingTabs[nextIndex].id);
    };

    switch (event.key) {
      case "ArrowRight":
      case "ArrowDown":
        event.preventDefault();
        focusTab((tabIndex + 1) % onboardingTabs.length);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        event.preventDefault();
        focusTab((tabIndex - 1 + onboardingTabs.length) % onboardingTabs.length);
        break;
      case "Home":
        event.preventDefault();
        focusTab(0);
        break;
      case "End":
        event.preventDefault();
        focusTab(onboardingTabs.length - 1);
        break;
      default:
        break;
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!user || isSaving) {
      return;
    }

    try {
      setIsSaving(true);
      setError(null);
      const resolvedFocusRole = getFormValue("focusRole", user.focusRole).trim();
      const resumeName = null;
      const selectedCertificateNames = certificateFiles.map((file) => file.name);
      const primaryCertificateName =
        selectedCertificateNames[0] || user.profileAssets.primaryCertificateName || "";
      const supportingCertificateNames =
        selectedCertificateNames.length > 1
          ? selectedCertificateNames.slice(1)
          : user.profileAssets.supportingCertificateNames;

      const fullLocation = form.country === "India"
        ? `${form.city}${form.city ? ", " : ""}${form.state}, India`
        : `${form.state}${form.state ? ", " : ""}${form.country}`;

      const metadata: OnboardingMetadata & {
        has_completed_onboarding: boolean;
        self_reported_skills: string[];
        profile_assets: {
          resumeName: string;
          primaryCertificateName: string;
          supportingCertificateNames: string[];
        };
      } = {
        has_completed_onboarding: true,
        self_reported_skills: parseSkills(getFormValue("skills", user.selfReportedSkills.join(", "))),
        bio: getFormValue("bio").trim(),
        location: fullLocation.trim(),
        target_industry: getFormValue("targetIndustry").trim(),
        profile_assets: {
          ...user.profileAssets,
          resumeName: resumeName ?? "",
          primaryCertificateName,
          supportingCertificateNames,
        },
      };

      // 1. Save mandatory profile data
      await apiFetch<ProfileRead>("/profile/me", {
        method: "PATCH",
        body: JSON.stringify({
          full_name: getFormValue("fullName", user.name).trim() || user.name,
          headline: getFormValue("currentRole", user.role).trim(),
          focus_role: resolvedFocusRole,
          weekly_goal: getFormValue("weeklyGoal", user.weeklyGoal).trim(),
          metadata,
        }),
      });

      // 2. Save preferences
      await apiFetch<UserPreferenceRead>("/settings/me", {
        method: "PATCH",
        body: JSON.stringify({
          folio_focus: resolvedFocusRole,
        }),
      });

      // 3. Upload artifacts if present
      const artifactUploads: Promise<unknown>[] = [];
      // Resume upload removed from onboarding

      for (const certificateFile of certificateFiles) {
        setStatusMessage(`Uploading ${certificateFile.name}...`);
        const formData = new FormData();
        formData.append("file", certificateFile);
        formData.append("file_type", "certificate");
        artifactUploads.push(
          apiFetch("/profile/me/artifacts", {
            method: "POST",
            body: formData,
          }),
        );
      }

      if (artifactUploads.length) {
        const uploadResults = await Promise.allSettled(artifactUploads);
        const failedUploads = uploadResults.filter((result) => result.status === "rejected");
        if (failedUploads.length) {
          console.error("Artifact upload failed:", failedUploads);
        }
      }

      // 4. Finalize
      setStatusMessage("Finalizing Workspace...");
      await refreshProfile();
      
      setStatusMessage("Success! Redirecting to Placement Quiz...");
      // Add a small delay so user can see the success state
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // We flip isSaving to false AFTER the delay. 
      // This will trigger the useEffect to redirect safely.
      setIsSaving(false);
    } catch (caught) {
      const message =
        caught instanceof ApiError ? caught.message : "Unable to finish onboarding right now.";
      setError(message);
      setIsSaving(false);
    }
  };

  if (isLoading || !user || (user.hasCompletedOnboarding && user.hasCompletedPlacement)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#fafafa]">
        <div className="h-10 w-10 rounded-full border-2 border-blue-600/20 border-t-blue-600 animate-spin" />
      </div>
    );
  }

  return (
    <AuthBackdrop>
      <div className="mx-auto flex min-h-screen w-full items-center justify-center p-4 sm:p-6 lg:p-10">
        <div className="grid w-full max-w-[1150px] overflow-visible rounded-[40px] bg-white shadow-[0_45px_100px_rgba(0,0,0,0.08)] lg:grid-cols-[460px_1fr]">
          <aside className="relative hidden overflow-hidden bg-[#0A1128] text-white lg:flex lg:flex-col lg:rounded-l-[40px]">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.18),transparent_55%),radial-gradient(circle_at_bottom_right,rgba(59,130,246,0.08),transparent_55%)]" />
            
            <div className="relative z-10 flex h-full flex-col p-10 xl:p-12">
              <div className="flex items-center justify-between">
                <Link href="/" aria-label="Back to home" className="transition hover:opacity-80">
                  <CeltmLogo compact className="h-12 w-12" />
                </Link>
                <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-[10px] font-black uppercase tracking-[0.28em] text-blue-50/80">
                  Onboarding
                </div>
              </div>

              <div className="mt-14 space-y-6">
                <div className="inline-flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.3em] text-blue-400">
                  <span className="h-1 w-8 rounded-full bg-blue-500" />
                  Profile Setup
                </div>
                <h1 className="text-4xl font-black leading-tight tracking-tight xl:text-5xl">
                  {heading}
                </h1>
                <p className="text-base leading-relaxed text-blue-100/70 xl:text-lg">
                  Complete your identity details so CELTM can personalize your learning path, track your skills, and guide your career growth.
                </p>
              </div>

              <div className="mt-12 space-y-5 rounded-3xl border border-white/10 bg-white/5 p-7 backdrop-blur-md">
                {[
                  "Initialize your skills inventory",
                  "Configure your career focus roles",
                  "Synchronize your dashboard roadmap"
                ].map((item) => (
                  <div key={item} className="flex items-start gap-4">
                    <div className="mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-blue-500/20 text-blue-400">
                      <span className="material-symbols-outlined text-[16px] font-bold">check</span>
                    </div>
                    <p className="text-[14px] font-medium leading-relaxed text-blue-50/80">{item}</p>
                  </div>
                ))}
              </div>

              <div className="mt-auto pt-10 text-[10px] font-bold uppercase tracking-[0.24em] text-blue-100/40">
                You can revisit these settings anytime later.
              </div>
            </div>
          </aside>

          <section className="relative flex flex-col bg-white p-8 sm:p-12 lg:rounded-r-[40px] lg:p-16">
            <div className="mx-auto w-full max-w-2xl">
              <div className="mb-12">
                <p className="text-[11px] font-black uppercase tracking-[0.24em] text-blue-600">
                  User Preferences
                </p>
                <h2 className="mt-4 text-3xl font-black tracking-tight text-[#0A1128] sm:text-4xl">
                  Setup your workspace.
                </h2>
                <p className="mt-3 text-[15px] leading-relaxed text-[#64748B]">
                  Tailor the CELTM platform to your professional goals. These answers bootstrap your personalized roadmap.
                </p>
              </div>

              <form className="space-y-6" onSubmit={(event) => void handleSubmit(event)}>
                <div className="space-y-4">
                  <div
                    role="tablist"
                    aria-label="Onboarding sections"
                    className="grid gap-3 rounded-[24px] border border-[#e7ebf7] bg-[#f7f9ff] p-3 sm:grid-cols-3"
                  >
                    {onboardingTabs.map((tab, index) => {
                      const isActive = tab.id === activeTab;

                      return (
                        <button
                          key={tab.id}
                          id={`onboarding-tab-${tab.id}`}
                          role="tab"
                          type="button"
                          aria-selected={isActive}
                          aria-controls={`onboarding-panel-${tab.id}`}
                          tabIndex={isActive ? 0 : -1}
                          onClick={() => moveToTab(tab.id)}
                          onKeyDown={(event) => handleTabKeyDown(event, index)}
                          className={`rounded-[18px] border px-4 py-3 text-left transition ${
                            isActive
                              ? "border-[#050505] bg-white text-[#050505] shadow-[0_18px_35px_rgba(0,0,0,0.10)]"
                              : "border-transparent bg-transparent text-[#7f89b6] hover:border-[#d9def0] hover:bg-white/90"
                          }`}
                        >
                          <span className="block text-[11px] font-black uppercase tracking-[0.22em]">
                            Step {index + 1}
                          </span>
                          <span className="mt-2 block text-sm font-bold">{tab.label}</span>
                        </button>
                      );
                    })}
                  </div>

                  <AnimatePresence mode="wait">
                    <motion.div
                      key={activeTab}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -20 }}
                      transition={{ duration: 0.3, ease: "easeInOut" }}
                      className="rounded-[24px] border border-slate-100 bg-[#fafafa] p-5 sm:p-6"
                    >
                      <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-blue-600/50">
                        {activeTabDefinition.label}
                      </p>
                      <h3 className="mt-3 text-2xl font-black tracking-tight text-[#0A1128]">
                        {activeTabDefinition.title}
                      </h3>
                      <p className="mt-2 text-sm leading-6 text-slate-500">
                        {activeTabDefinition.description}
                      </p>

                    {activeTab === "identity" ? (
                      <div
                        id="onboarding-panel-identity"
                        role="tabpanel"
                        aria-labelledby="onboarding-tab-identity"
                        className="mt-6 grid gap-5 md:grid-cols-2"
                      >
                        <label className="block">
                          <span className="mb-2 block text-sm font-semibold text-[#6f75a3]">
                            Full Name
                          </span>
                          <input
                            required
                            value={getFormValue("fullName", user?.name ?? "")}
                            onChange={(event) => handleChange("fullName", event.target.value)}
                            className="h-12 w-full rounded-xl border border-slate-200 bg-white px-4 text-[15px] text-[#0A1128] outline-none transition-all focus:border-blue-600 focus:ring-4 focus:ring-blue-600/5 placeholder:text-slate-300"
                            placeholder="Your name"
                          />
                        </label>

                        <label className="block">
                          <span className="mb-2 block text-sm font-semibold text-[#6f75a3]">
                            Current Role
                          </span>
                          <select
                            value={getFormValue("currentRole", user?.role ?? "")}
                            onChange={(event) => handleChange("currentRole", event.target.value)}
                            className="auth-input-glow h-12 w-full rounded-xl border border-[#d9def0] bg-white px-4 text-[15px] text-[#5e6696] outline-none"
                          >
                            <option value="">Select your role...</option>
                            <option value="Student">Student</option>
                            <option value="Analyst">Analyst</option>
                            <option value="Engineer">Engineer</option>
                            <option value="Designer">Designer</option>
                            <option value="Manager">Manager</option>
                            <option value="Other">Other</option>
                          </select>
                        </label>

                        <div className="md:col-span-2 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                          <label className="block">
                            <span className="mb-2 block text-sm font-semibold text-[#6f75a3]">
                              Country
                            </span>
                            <select
                              value={getFormValue("country", "India")}
                              onChange={(event) => {
                                handleChange("country", event.target.value);
                                handleChange("state", "");
                                handleChange("city", "");
                              }}
                              className="auth-input-glow h-12 w-full rounded-xl border border-[#d9def0] bg-white px-4 text-[15px] text-[#5e6696] outline-none"
                            >
                              <option value="">Select country...</option>
                              {COUNTRIES.map(c => <option key={c} value={c}>{c}</option>)}
                            </select>
                          </label>

                          {getFormValue("country") === "India" ? (
                            <>
                              <label className="block">
                                <span className="mb-2 block text-sm font-semibold text-[#6f75a3]">
                                  State
                                </span>
                                <select
                                  value={getFormValue("state")}
                                  onChange={(event) => {
                                    handleChange("state", event.target.value);
                                    handleChange("city", "");
                                  }}
                                  className="auth-input-glow h-12 w-full rounded-xl border border-[#d9def0] bg-white px-4 text-[15px] text-[#5e6696] outline-none"
                                >
                                  <option value="">Select state...</option>
                                  {Object.keys(INDIA_LOCATIONS).map(s => <option key={s} value={s}>{s}</option>)}
                                </select>
                              </label>

                              <label className="block">
                                <span className="mb-2 block text-sm font-semibold text-[#6f75a3]">
                                  City
                                </span>
                                <select
                                  disabled={!getFormValue("state")}
                                  value={getFormValue("city")}
                                  onChange={(event) => handleChange("city", event.target.value)}
                                  className="auth-input-glow h-12 w-full rounded-xl border border-[#d9def0] bg-white px-4 text-[15px] text-[#5e6696] outline-none disabled:opacity-50"
                                >
                                  <option value="">Select city...</option>
                                  {(INDIA_LOCATIONS[getFormValue("state") as keyof typeof INDIA_LOCATIONS] || []).map(c => (
                                    <option key={c} value={c}>{c}</option>
                                  ))}
                                </select>
                              </label>
                            </>
                          ) : (
                            <label className="block">
                              <span className="mb-2 block text-sm font-semibold text-[#6f75a3]">
                                Specify Location
                              </span>
                              <input
                                value={getFormValue("state")}
                                onChange={(event) => handleChange("state", event.target.value)}
                                className="auth-input-glow h-12 w-full rounded-xl border border-[#d9def0] bg-white px-4 text-[15px] text-[#5e6696] outline-none"
                                placeholder="e.g. California, USA"
                              />
                            </label>
                          )}
                        </div>

                        <label className="block">
                          <span className="mb-2 block text-sm font-semibold text-[#6f75a3]">
                            Target Industry
                          </span>
                          <select
                            value={getFormValue("targetIndustry")}
                            onChange={(event) => handleChange("targetIndustry", event.target.value)}
                            className="auth-input-glow h-12 w-full rounded-xl border border-[#d9def0] bg-white px-4 text-[15px] text-[#5e6696] outline-none"
                          >
                            <option value="">Select target industry...</option>
                            <option value="Healthtech">Healthtech</option>
                            <option value="Fintech">Fintech</option>
                            <option value="Enterprise Software">Enterprise Software</option>
                            <option value="AI / Machine Learning">AI / Machine Learning</option>
                            <option value="E-Commerce">E-Commerce</option>
                            <option value="Research">Research</option>
                            <option value="Other">Other</option>
                          </select>
                        </label>
                        <label className="block">
                          <span className="mb-1 flex items-center gap-2 text-sm font-semibold text-[#6f75a3]">
                            Certificates Upload
                            <span className="rounded-full bg-[#e7ebf7] px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.18em] text-[#9099c0]">optional</span>
                          </span>
                          <div className="rounded-2xl border border-dashed border-[#c9d1ec] bg-[#f7f9ff] p-4">
                            <input
                              type="file"
                              accept=".pdf,.doc,.docx,.txt,image/*"
                              multiple
                              onChange={(event) =>
                                setCertificateFiles(Array.from(event.target.files ?? []))
                              }
                              className="block w-full text-sm text-[#5e6696] file:mr-4 file:rounded-full file:border-0 file:bg-[#0F172A] file:px-4 file:py-2 file:text-xs file:font-bold file:uppercase file:tracking-[0.18em] file:text-white"
                            />
                            <p className="mt-3 text-xs leading-6 text-[#6f75a3]">
                              Add certificates or licenses so CELTM can align subjects and personalize follow-up assessments.
                            </p>
                            <p className="mt-2 text-xs font-semibold text-[#2b3562]">
                              {certificateFiles.length
                                ? `Selected: ${certificateFiles.map((file) => file.name).join(", ")}`
                                : user?.profileAssets.primaryCertificateName
                                  ? `Current certificates: ${[
                                      user.profileAssets.primaryCertificateName,
                                      ...user.profileAssets.supportingCertificateNames,
                                    ]
                                      .filter(Boolean)
                                      .join(", ")}`
                                  : "No certificates selected"}
                            </p>
                          </div>
                        </label>
                      </div>
                    ) : null}

                    {activeTab === "direction" ? (
                      <div
                        id="onboarding-panel-direction"
                        role="tabpanel"
                        aria-labelledby="onboarding-tab-direction"
                        className="mt-6 grid gap-5 md:grid-cols-2"
                      >
                        <label className="block">
                          <span className="mb-2 block text-sm font-semibold text-[#6f75a3]">
                            Focus Role
                          </span>
                          <select
                            required
                            value={getFormValue("focusRole", user?.focusRole ?? "")}
                            onChange={(event) => handleChange("focusRole", event.target.value)}
                            className="auth-input-glow h-12 w-full rounded-xl border border-[#d9def0] bg-white px-4 text-[15px] text-[#5e6696] outline-none"
                          >
                            <option value="">Select focus role...</option>
                            <option value="Machine Learning Engineer">Machine Learning Engineer</option>
                            <option value="Frontend Developer">Frontend Developer</option>
                            <option value="Backend Developer">Backend Developer</option>
                            <option value="Data Scientist">Data Scientist</option>
                            <option value="Product Manager">Product Manager</option>
                            <option value="UX/UI Designer">UX/UI Designer</option>
                          </select>
                        </label>

                        <label className="block">
                          <span className="mb-2 block text-sm font-semibold text-[#6f75a3]">
                            Weekly Goal
                          </span>
                          <input
                            required
                            value={getFormValue("weeklyGoal", user?.weeklyGoal ?? "")}
                            onChange={(event) => handleChange("weeklyGoal", event.target.value)}
                            className="auth-input-glow h-12 w-full rounded-xl border border-[#d9def0] bg-white px-4 text-[15px] text-[#5e6696] outline-none placeholder:text-[#c2c7dd]"
                            placeholder="Finish 2 assessments and 1 mock interview"
                          />
                        </label>
                      </div>
                    ) : null}

                    {activeTab === "background" ? (
                      <div
                        id="onboarding-panel-background"
                        role="tabpanel"
                        aria-labelledby="onboarding-tab-background"
                        className="mt-6 space-y-5"
                      >
                        <label className="block">
                          <span className="mb-2 block text-sm font-semibold text-[#6f75a3]">
                            Skills You Already Bring
                          </span>
                          <select
                            value={getFormValue("skills", user?.selfReportedSkills.join(", ") ?? "")}
                            onChange={(event) => handleChange("skills", event.target.value)}
                            className="auth-input-glow h-12 w-full rounded-xl border border-[#d9def0] bg-white px-4 text-[15px] text-[#5e6696] outline-none"
                          >
                            <option value="">Select your primary skills...</option>
                            <option value="Python, ML Ops, SQL">Python, ML Ops, SQL</option>
                            <option value="React, Node.js, TS">React, Node.js, TS</option>
                            <option value="Figma, UI/UX">Figma, UI/UX</option>
                            <option value="Management, Agile">Management, Agile</option>
                            <option value="No prior skills">No prior skills</option>
                          </select>
                        </label>

                        <label className="block">
                          <span className="mb-2 block text-sm font-semibold text-[#6f75a3]">
                            Professional Bio
                          </span>
                          <textarea
                            rows={5}
                            value={getFormValue("bio")}
                            onChange={(event) => handleChange("bio", event.target.value)}
                            className="auth-input-glow w-full rounded-2xl border border-[#d9def0] bg-white px-4 py-3 text-[15px] text-[#5e6696] outline-none placeholder:text-[#c2c7dd]"
                            placeholder="What should CELTM keep in mind when it tailors your learning path?"
                          />
                        </label>

                        {/* Resume upload moved to dashboard popup */}
                      </div>
                    ) : null}
                    </motion.div>
                  </AnimatePresence>
                </div>

                {error ? <p className="text-sm text-red-500">{error}</p> : null}

                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <button
                    type="button"
                    onClick={() => moveTabByOffset(-1)}
                    disabled={activeTabIndex === 0 || isSaving}
                    className="inline-flex h-12 items-center justify-center rounded-xl border border-[#d9def0] px-5 text-sm font-semibold text-[#5e6696] transition hover:border-[#c4cbe5] hover:bg-[#f7f9ff] disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    Previous
                  </button>

                  {isLastTab ? (
                    <button
                      type="submit"
                      disabled={isSaving}
                      className="inline-flex h-12 items-center justify-center gap-3 rounded-xl bg-[#0F172A] px-6 text-sm font-bold tracking-[0.24em] text-white transition hover:bg-[#1E293B] disabled:cursor-progress disabled:opacity-70"
                    >
                      {isSaving ? (
                        <>
                          <span className="h-4 w-4 rounded-full border-2 border-white/35 border-t-white animate-spin" />
                          <span>{statusMessage || "Finalizing..."}</span>
                        </>
                      ) : (
                        <span>Proceed to Placement Quiz</span>
                      )}
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => moveTabByOffset(1)}
                      disabled={isSaving}
                      className="inline-flex h-12 items-center justify-center rounded-xl bg-blue-600 px-6 text-sm font-bold tracking-[0.2em] text-white shadow-[0_10px_20px_rgba(37,99,235,0.2)] transition hover:bg-blue-700 disabled:cursor-progress disabled:opacity-70"
                    >
                      NEXT SECTION
                    </button>
                  )}
                </div>
              </form>
            </div>
          </section>
        </div>
      </div>
    </AuthBackdrop>
  );
}
