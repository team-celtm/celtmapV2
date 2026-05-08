"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, apiFetch, apiFetchBlob } from "@/lib/api";
import type {
  ArtifactRead,
  DashboardSummary,
  ProfileRead,
  RoleFitRead,
  SkillRead,
  UserPreferenceRead,
} from "@/lib/celtm";
import { formatDate, toTitleCase } from "@/lib/celtm";
import { FormSkeleton, ListSkeleton, SkeletonPulse } from "@/components/common/Skeletons";
import { resolveStorageAssetUrl } from "@/lib/storage";
import { useAuth } from "@/contexts/AuthContext";

interface ProfileMetadata {
  bio?: string;
  location?: string;
  target_industry?: string;
}

type SettingsTabKey = "profile" | "passport" | "notifications" | "credentials";

function sanitizeFileName(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "celtm-passport";
}

export default function SettingsPage() {
  const { refreshProfile } = useAuth();
  const [activeTab, setActiveTab] = useState<SettingsTabKey>("profile");
  const [profile, setProfile] = useState<ProfileRead | null>(null);
  const [settings, setSettings] = useState<UserPreferenceRead | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRead[]>([]);
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [roleFit, setRoleFit] = useState<RoleFitRead | null>(null);
  const [skills, setSkills] = useState<SkillRead[]>([]);
  const [form, setForm] = useState({
    fullName: "",
    headline: "",
    focusRole: "",
    weeklyGoal: "",
    bio: "",
    location: "",
    targetIndustry: "",
  });
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactRead | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [uploadingArtifact, setUploadingArtifact] = useState(false);
  const [deletingArtifactId, setDeletingArtifactId] = useState<string | null>(null);
  const [replacingArtifactId, setReplacingArtifactId] = useState<string | null>(null);
  const [menuOpenForArtifact, setMenuOpenForArtifact] = useState<string | null>(null);
  const [artifactToDelete, setArtifactToDelete] = useState<ArtifactRead | null>(null);
  const [isExportingPassport, setIsExportingPassport] = useState(false);
  const [notificationPermission, setNotificationPermission] = useState<NotificationPermission | "unsupported">("unsupported");
  const [error, setError] = useState<string | null>(null);

  const profileInputRef = useRef<HTMLInputElement>(null);
  const proofInputRef = useRef<HTMLInputElement>(null);
  const replaceInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let isMounted = true;

    const loadSettings = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const [profilePayload, settingsPayload, artifactsPayload, summaryPayload, roleFitPayload, skillsPayload] = await Promise.all([
          apiFetch<ProfileRead>("/profile/me"),
          apiFetch<UserPreferenceRead>("/settings/me"),
          apiFetch<ArtifactRead[]>("/profile/me/artifacts"),
          apiFetch<DashboardSummary>("/dashboard/summary").catch(() => null),
          apiFetch<RoleFitRead>("/skills/me/role-fit").catch(() => null),
          apiFetch<SkillRead[]>("/skills/me").catch(() => []),
        ]);

        if (!isMounted) {
          return;
        }

        const metadata = (profilePayload.metadata ?? {}) as ProfileMetadata;
        setProfile(profilePayload);
        setSettings(settingsPayload);
        setArtifacts(artifactsPayload);
        setSummary(summaryPayload);
        setRoleFit(roleFitPayload);
        setSkills(skillsPayload);
        setForm({
          fullName: profilePayload.full_name ?? "",
          headline: profilePayload.headline ?? "",
          focusRole: profilePayload.focus_role ?? "",
          weeklyGoal: profilePayload.weekly_goal ?? "",
          bio: metadata.bio ?? "",
          location: metadata.location ?? "",
          targetIndustry: metadata.target_industry ?? "",
        });
      } catch (caught) {
        if (!isMounted) {
          return;
        }
        const message = caught instanceof ApiError ? caught.message : "Failed to load settings.";
        setError(message);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    void loadSettings();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      setNotificationPermission("unsupported");
      return;
    }

    setNotificationPermission(Notification.permission);
  }, []);

  const currentAvatar = useMemo(() => {
    return avatarPreview ?? resolveStorageAssetUrl(profile?.avatar_url) ?? "https://ui-avatars.com/api/?name=CELTM+User&background=6366f1&color=fff";
  }, [avatarPreview, profile?.avatar_url]);
  const nameFromEmail = profile?.email?.split("@")[0] || "";
  const displayName = 
    form.fullName || 
    (profile?.full_name && profile.full_name !== nameFromEmail ? profile.full_name : null) || 
    profile?.full_name || 
    nameFromEmail || 
    "CELTM user";
  const readinessLabel = summary ? `${Math.round(summary.readiness_score)}%` : "Pending";
  const roleMatchLabel = roleFit?.role_name || form.focusRole || "In progress";
  const topSkillLabels = [...skills]
    .sort((left, right) => right.verified_score - left.verified_score)
    .slice(0, 6)
    .map((skill) => `${skill.skill_name} ${Math.round(skill.verified_score)}%`);
  const resumeArtifact = useMemo(
    () =>
      artifacts.find((artifact) => artifact.file_type.toLowerCase() === "resume") ?? null,
    [artifacts],
  );
  const resumePreview = useMemo(() => {
    const extractedText = resumeArtifact?.extracted_text?.trim();
    if (!extractedText) {
      return "No parsed resume text available yet.";
    }

    return extractedText.length > 240 ? `${extractedText.slice(0, 240)}...` : extractedText;
  }, [resumeArtifact]);

  const handleAvatarUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      setUploadingAvatar(true);
      setError(null);
      setAvatarPreview(URL.createObjectURL(file));
      const formData = new FormData();
      formData.append("file", file);
      const updatedProfile = await apiFetch<ProfileRead>("/profile/me/avatar", {
        method: "POST",
        body: formData,
      });
      setProfile(updatedProfile);
      await refreshProfile();
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Failed to upload the profile image.";
      setError(message);
    } finally {
      setUploadingAvatar(false);
    }
  };

  const handleArtifactUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    try {
      setUploadingArtifact(true);
      setError(null);
      const formData = new FormData();
      formData.append("file", file);
      formData.append("file_type", "certificate");
      const artifact = await apiFetch<ArtifactRead>("/profile/me/artifacts", {
        method: "POST",
        body: formData,
      });
      setArtifacts((current) => [artifact, ...current]);
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Failed to upload the credential artifact.";
      setError(message);
    } finally {
      setUploadingArtifact(false);
    }
  };

  const confirmDelete = async () => {
    if (!artifactToDelete) return;
    const artifactId = artifactToDelete.id;

    try {
      setDeletingArtifactId(artifactId);
      setError(null);
      await apiFetch(`/profile/me/artifacts/${artifactId}`, {
        method: "DELETE",
      });
      setArtifacts((current) => current.filter((a) => a.id !== artifactId));
      if (selectedArtifact?.id === artifactId) {
        setSelectedArtifact(null);
      }
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Failed to delete the credential.";
      setError(message);
    } finally {
      setDeletingArtifactId(null);
      setArtifactToDelete(null);
    }
  };

  const handleReplaceUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file || !replacingArtifactId) {
      return;
    }

    try {
      setError(null);
      const formData = new FormData();
      formData.append("file", file);
      
      const updatedArtifact = await apiFetch<ArtifactRead>(`/profile/me/artifacts/${replacingArtifactId}`, {
        method: "PUT",
        body: formData,
      });
      
      setArtifacts((current) => current.map((a) => a.id === replacingArtifactId ? updatedArtifact : a));
      if (selectedArtifact?.id === replacingArtifactId) {
        setSelectedArtifact(updatedArtifact);
      }
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Failed to replace the credential artifact.";
      setError(message);
    } finally {
      setReplacingArtifactId(null);
      if (replaceInputRef.current) {
        replaceInputRef.current.value = "";
      }
    }
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);
      setSaveSuccess(false);
      setError(null);

      const updatedProfile = await apiFetch<ProfileRead>("/profile/me", {
        method: "PATCH",
        body: JSON.stringify({
          full_name: form.fullName,
          headline: form.headline,
          focus_role: form.focusRole,
          weekly_goal: form.weeklyGoal,
          metadata: {
            ...(profile?.metadata ?? {}),
            bio: form.bio,
            location: form.location,
            target_industry: form.targetIndustry,
          },
        }),
      });

      const updatedSettings = await apiFetch<UserPreferenceRead>("/settings/me", {
        method: "PATCH",
        body: JSON.stringify({
          folio_focus: form.focusRole,
        }),
      });

      setProfile(updatedProfile);
      setSettings(updatedSettings);
      setSaveSuccess(true);
      await refreshProfile();
      window.setTimeout(() => setSaveSuccess(false), 3000);
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Failed to persist settings changes.";
      setError(message);
    } finally {
      setIsSaving(false);
    }
  };

  const updateBooleanSetting = async (key: "desktop_notifications" | "weekly_digest" | "folio_reminders") => {
    if (!settings) {
      return;
    }

    try {
      setError(null);
      if (key === "desktop_notifications" && !settings.desktop_notifications) {
        if (typeof window === "undefined" || !("Notification" in window)) {
          setError("This browser does not support desktop notifications.");
          setNotificationPermission("unsupported");
          return;
        }

        let permission = Notification.permission;
        if (permission === "default") {
          permission = await Notification.requestPermission();
        }
        setNotificationPermission(permission);

        if (permission !== "granted") {
          setError("Desktop notifications are blocked in this browser. Enable them in your browser settings and try again.");
          return;
        }
      }

      const updated = await apiFetch<UserPreferenceRead>("/settings/me/notifications", {
        method: "PATCH",
        body: JSON.stringify({
          [key]: !settings[key],
        }),
      });
      setSettings(updated);
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Failed to update notification preferences.";
      setError(message);
    }
  };

  const updateSecurityMode = async (securityMode: string) => {
    try {
      setError(null);
      const updated = await apiFetch<UserPreferenceRead>("/settings/me/security", {
        method: "PATCH",
        body: JSON.stringify({
          security_mode: securityMode,
        }),
      });
      setSettings(updated);
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Failed to update security mode.";
      setError(message);
    }
  };

  const handlePassportExport = async () => {
    try {
      setIsExportingPassport(true);
      setError(null);

      const blob = await apiFetchBlob("/reports/me/passport.pdf");
      const fileName = `${sanitizeFileName(displayName)}-skill-passport.pdf`;
      const blobUrl = URL.createObjectURL(blob);

      const downloadLink = document.createElement("a");
      downloadLink.href = blobUrl;
      downloadLink.download = fileName;
      downloadLink.click();

      window.setTimeout(() => {
        URL.revokeObjectURL(blobUrl);
      }, 1000);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Failed to export the CELTM passport.";
      setError(message);
    } finally {
      window.setTimeout(() => setIsExportingPassport(false), 500);
    }
  };

  // Progressive loading: Page shell renders immediately
  const isProfileLoaded = !!profile && !isLoading;
  const isArtifactsLoaded = artifacts.length > 0 || !isLoading;

  return (
    <div className="w-full max-w-[1520px] mx-auto space-y-6 animate-fade-in pb-12">
      {error ? (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-5 py-4 text-sm text-red-400">
          {error}
        </div>
      ) : null}

      <div className="grid grid-cols-12 gap-8">
        <aside className="col-span-12 lg:col-span-3">
          <div className="flex flex-col gap-2">
            <h1 className="text-3xl font-extrabold tracking-tight text-on-surface mb-6">Settings</h1>
            {[
              { key: "profile" as const, icon: "person", label: "Personal Profile" },
              { key: "passport" as const, icon: "badge", label: "Passport Export" },
              { key: "notifications" as const, icon: "notifications_active", label: "Notifications" },
              { key: "credentials" as const, icon: "workspace_premium", label: "Credentials" },
            ].map((item) => {
              const isActive = activeTab === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setActiveTab(item.key)}
                  className={`lift-tile flex items-center gap-3 rounded-full px-6 py-3 text-left transition-all ${
                    isActive
                      ? "bg-primary/10 text-primary border border-primary/15"
                      : "bg-surface-container text-on-surface-variant border border-outline-variant/10 dark:border-transparent hover:border-primary/15 hover:text-on-surface"
                  }`}
                >
                  <span className="material-symbols-outlined">{item.icon}</span>
                  <span className={`text-sm uppercase tracking-widest ${isActive ? "font-bold" : "font-medium"}`}>{item.label}</span>
                </button>
              );
            })}
          </div>
        </aside>

        <div className="col-span-12 lg:col-span-9 space-y-8">
          {activeTab === "profile" ? (
          <section className="clay-card rounded-[32px] p-8 flex flex-col items-start relative overflow-hidden">
            <div className="absolute top-0 right-0 w-64 h-64 bg-primary/10 rounded-full blur-3xl -mr-32 -mt-32" />

            <div className="flex flex-col md:flex-row gap-8 w-full z-10 relative">
              <div className="flex flex-col items-center gap-4">
                <div
                  className="relative w-32 h-32 rounded-3xl bg-surface-container-highest flex items-center justify-center overflow-hidden flex-shrink-0 group cursor-pointer border-2 border-transparent hover:border-primary/50 transition-all shadow-xl"
                  onClick={() => profileInputRef.current?.click()}
                >
                  <img
                    alt="User Avatar"
                    className="w-full h-full object-cover"
                    src={currentAvatar}
                    onError={(event) => {
                      event.currentTarget.onerror = null;
                      event.currentTarget.src = "https://ui-avatars.com/api/?name=CELTM+User&background=6366f1&color=fff";
                    }}
                  />
                  <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <span className="material-symbols-outlined text-white text-3xl">{uploadingAvatar ? "sync" : "add_a_photo"}</span>
                  </div>
                  <input type="file" ref={profileInputRef} className="hidden" accept="image/*" onChange={handleAvatarUpload} />
                </div>
                <span className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
                  {uploadingAvatar ? "Uploading..." : "Update Photo"}
                </span>
              </div>

              {isProfileLoaded ? (
                <div className="flex-grow space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant ml-1">Full Name</label>
                      <input
                        type="text"
                        className="w-full rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-3 font-bold text-on-surface transition-all focus:outline-none focus:ring-2 focus:ring-primary/40"
                        value={form.fullName}
                        onChange={(event) => setForm((current) => ({ ...current, fullName: event.target.value }))}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant ml-1">Current Role</label>
                      <input
                        type="text"
                        className="w-full rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-3 font-bold text-on-surface transition-all focus:outline-none focus:ring-2 focus:ring-primary/40"
                        value={form.headline}
                        onChange={(event) => setForm((current) => ({ ...current, headline: event.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant ml-1">Focus Role</label>
                      <input
                        type="text"
                        className="w-full rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-3 font-bold text-on-surface transition-all focus:outline-none focus:ring-2 focus:ring-primary/40"
                        value={form.focusRole}
                        onChange={(event) => setForm((current) => ({ ...current, focusRole: event.target.value }))}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant ml-1">Location</label>
                      <input
                        type="text"
                        className="w-full rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-3 font-bold text-on-surface transition-all focus:outline-none focus:ring-2 focus:ring-primary/40"
                        value={form.location}
                        onChange={(event) => setForm((current) => ({ ...current, location: event.target.value }))}
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant ml-1">Target Industry / Goals</label>
                    <input
                      type="text"
                      className="w-full rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-3 font-bold text-on-surface transition-all focus:outline-none focus:ring-2 focus:ring-primary/40"
                      value={form.targetIndustry}
                      onChange={(event) => setForm((current) => ({ ...current, targetIndustry: event.target.value }))}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant ml-1">Weekly Goal</label>
                    <input
                      type="text"
                      className="w-full rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-3 font-bold text-on-surface transition-all focus:outline-none focus:ring-2 focus:ring-primary/40"
                      value={form.weeklyGoal}
                      onChange={(event) => setForm((current) => ({ ...current, weeklyGoal: event.target.value }))}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant ml-1">Professional Bio</label>
                    <textarea
                      rows={4}
                      className="w-full resize-none rounded-2xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low px-5 py-3 font-medium text-on-surface transition-all focus:outline-none focus:ring-2 focus:ring-primary/40"
                      value={form.bio}
                      onChange={(event) => setForm((current) => ({ ...current, bio: event.target.value }))}
                    />
                  </div>
                </div>
              ) : (
                <div className="flex-grow">
                  <FormSkeleton />
                </div>
              )}
            </div>

            <div className="w-full flex items-center justify-end mt-8 border-t border-outline-variant/12 dark:border-transparent pt-6 z-10 relative">
              {saveSuccess ? <span className="text-emerald-500 font-bold text-sm tracking-widest uppercase mr-6 animate-pulse">Changes Saved</span> : null}
              <button
                onClick={() => void handleSave()}
                disabled={isSaving}
                className="px-8 py-3 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-full text-sm font-bold shadow-lg shadow-indigo-500/20 hover:scale-105 active:scale-95 transition-all flex items-center gap-2 disabled:opacity-50"
              >
                <span className={`material-symbols-outlined text-sm ${isSaving ? "animate-spin" : ""}`}>{isSaving ? "sync" : "verified_user"}</span>
                {isSaving ? "Saving..." : "Update Profile"}
              </button>
            </div>
          </section>
          ) : null}

          {activeTab === "passport" ? (
          <section className="clay-card rounded-[32px] p-8 relative overflow-hidden group">
            <div className="absolute -right-12 -top-12 w-48 h-48 bg-gradient-to-br from-indigo-500/10 to-purple-500/10 rounded-full blur-3xl group-hover:scale-150 transition-transform duration-700" />
            <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
              <div className="flex items-start gap-5">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 shrink-0">
                  <span className="material-symbols-outlined text-white text-3xl">verified</span>
                </div>
                <div>
                  <h3 className="text-xl font-bold tracking-tight text-on-surface mb-1">CELTM Passport</h3>
                  <p className="text-on-surface-variant text-sm leading-relaxed max-w-lg">
                    Export a branded PDF skill passport with your identity, role focus, verified skills, uploaded credentials, and parsed resume details.
                  </p>
                  <div className="flex flex-wrap gap-2 mt-3">
                    {[
                      roleMatchLabel,
                      readinessLabel,
                      settings?.security_mode ? toTitleCase(settings.security_mode) : "Security mode",
                      `${artifacts.length} credentials`,
                    ].map((tag) => (
                      <span key={tag} className="px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-500 text-[10px] font-bold uppercase tracking-wider">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => void handlePassportExport()}
                disabled={isExportingPassport}
                className="px-8 py-3.5 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-full text-sm font-bold shadow-lg shadow-indigo-500/20 whitespace-nowrap shrink-0 transition-all hover:scale-[1.02] disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {isExportingPassport ? "Exporting..." : "Export PDF Passport"}
              </button>
            </div>

            <div className="relative z-10 mt-8 grid gap-4 md:grid-cols-[1.05fr_0.95fr]">
              <div className="lift-card rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low/70 p-5">
                <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-primary">Passport contents</p>
                <div className="space-y-3 text-sm leading-7 text-on-surface-variant">
                  <p>Identity: {displayName}{profile?.email ? ` • ${profile.email}` : ""}</p>
                  <p>Direction: {form.focusRole || "Not set"} • {form.targetIndustry || "No target industry yet"}</p>
                  <p>Weekly goal: {form.weeklyGoal || "Not set"}</p>
                  <p>Bio summary: {form.bio || "No professional bio saved yet."}</p>
                  <p>Resume file: {resumeArtifact?.file_name || "No resume uploaded yet."}</p>
                  <p>Resume details: {resumePreview}</p>
                </div>
              </div>
              <div className="lift-card rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low/70 p-5">
                <p className="mb-3 text-[10px] font-black uppercase tracking-[0.2em] text-primary">Verified snapshot</p>
                <div className="flex flex-wrap gap-2">
                  {(topSkillLabels.length ? topSkillLabels : ["No verified skills recorded yet"]).map((item) => (
                    <span key={item} className="rounded-full border border-primary/15 bg-primary/10 px-3 py-1.5 text-[11px] font-bold text-primary">
                      {item}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </section>
          ) : null}

          {activeTab === "notifications" ? (
          <section className="clay-card rounded-[32px] p-8 relative overflow-hidden">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h3 className="text-xl font-bold tracking-tight">Security & Notifications</h3>
                <p className="text-on-surface-variant text-sm mt-1">Persisted user preferences and security mode.</p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {([
                {
                  key: "desktop_notifications" as const,
                  title: "Desktop Notifications",
                  description: "Receive real-time alerts for new evaluations and hidden skill discoveries.",
                  enabled: settings?.desktop_notifications ?? false,
                },
                {
                  key: "weekly_digest" as const,
                  title: "Weekly Digest",
                  description: "Send the weekly CELTM progress digest to the authenticated email address.",
                  enabled: settings?.weekly_digest ?? false,
                },
                {
                  key: "folio_reminders" as const,
                  title: "Folio Reminders",
                  description: "Remind me to refresh credentials and portfolio evidence on schedule.",
                  enabled: settings?.folio_reminders ?? false,
                },
              ]).map((item) => (
                <button
                  key={item.key}
                  onClick={() => void updateBooleanSetting(item.key)}
                  className="lift-tile text-left rounded-3xl border border-outline-variant/10 dark:border-transparent bg-surface-container-low/50 p-5 hover:border-primary/20 transition-all"
                >
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-bold text-on-surface">{item.title}</h4>
                    <span className={`px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${
                      item.enabled ? "bg-emerald-500/10 text-emerald-500" : "bg-surface-container text-on-surface-variant"
                    }`}>
                      {item.enabled ? "Enabled" : "Disabled"}
                    </span>
                  </div>
                  <p className="text-sm text-on-surface-variant leading-relaxed">{item.description}</p>
                </button>
              ))}

              <div className="lift-card rounded-3xl border border-outline-variant/10 dark:border-transparent bg-surface-container-low/50 p-5">
                <h4 className="text-sm font-bold text-on-surface mb-3">Security Mode</h4>
                <p className="text-sm text-on-surface-variant leading-relaxed mb-5">
                  Current mode: <span className="font-bold text-on-surface">{toTitleCase(settings?.security_mode ?? "standard")}</span>
                </p>
                <div className="flex flex-wrap gap-3">
                  {["standard", "strict"].map((mode) => (
                    <button
                      key={mode}
                      onClick={() => void updateSecurityMode(mode)}
                      className={`px-4 py-2 rounded-full text-xs font-black uppercase tracking-widest transition-all ${
                        settings?.security_mode === mode ? "bg-primary text-white" : "bg-surface-container text-on-surface-variant"
                      }`}
                    >
                      {toTitleCase(mode)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="lift-card rounded-3xl border border-outline-variant/10 dark:border-transparent bg-surface-container-low/50 p-5">
                <h4 className="mb-3 text-sm font-bold text-on-surface">Browser Notification Permission</h4>
                <p className="mb-5 text-sm leading-relaxed text-on-surface-variant">
                  Status:{" "}
                  <span className="font-bold text-on-surface">
                    {notificationPermission === "unsupported"
                      ? "Unsupported"
                      : toTitleCase(notificationPermission)}
                  </span>
                </p>
                <p className="text-sm leading-relaxed text-on-surface-variant">
                  Turning on desktop alerts now checks actual browser permission first, so the toggle reflects a real deliverable experience instead of only changing a saved flag.
                </p>
              </div>
            </div>
          </section>
          ) : null}

          {activeTab === "credentials" ? (
          <section className="clay-card rounded-[32px] p-8 relative overflow-hidden">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h3 className="text-xl font-bold tracking-tight">Certifications & Achievements</h3>
                <p className="text-on-surface-variant text-sm mt-1">Uploaded credentials stored as career artifacts.</p>
              </div>
              <button
                onClick={() => proofInputRef.current?.click()}
                className="px-6 py-2.5 bg-surface-container-highest hover:bg-surface-container rounded-full text-xs font-black uppercase tracking-widest flex items-center gap-2 transition-all cursor-pointer border border-outline-variant/12 dark:border-transparent"
              >
                <span className={`material-symbols-outlined text-sm ${uploadingArtifact ? "animate-spin" : ""}`}>{uploadingArtifact ? "sync" : "add_circle"}</span>
                {uploadingArtifact ? "Uploading..." : "Add Credential"}
              </button>
              <input type="file" ref={proofInputRef} className="hidden" accept=".pdf,image/*" onChange={handleArtifactUpload} />
            </div>

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-3 max-h-[52rem] overflow-y-auto pr-2 custom-scrollbar min-h-[300px]">
              {isArtifactsLoaded ? (
                <>
                  <input type="file" ref={replaceInputRef} className="hidden" accept=".pdf,image/*" onChange={handleReplaceUpload} />
                  {artifacts.map((artifact) => (
                    <div key={artifact.id} className="relative group">
                      <button
                        className={`w-full lift-card rounded-3xl border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-4 flex flex-col group-hover:border-primary/30 transition-all cursor-pointer shadow-lg text-left ${(deletingArtifactId === artifact.id || replacingArtifactId === artifact.id) ? 'opacity-50' : ''}`}
                        onClick={() => setSelectedArtifact(artifact)}
                        disabled={deletingArtifactId === artifact.id || replacingArtifactId === artifact.id}
                      >
                        <div className="w-full h-32 bg-black/20 rounded-2xl overflow-hidden relative mb-4 flex items-center justify-center">
                          <span className="material-symbols-outlined text-5xl text-primary/70">
                            {artifact.file_name.toLowerCase().endsWith(".pdf") ? "description" : "image"}
                          </span>
                          {(deletingArtifactId === artifact.id || replacingArtifactId === artifact.id) && (
                            <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                              <span className="material-symbols-outlined text-white text-3xl animate-spin">sync</span>
                            </div>
                          )}
                        </div>
                        <div className="flex items-start justify-between px-1 gap-3">
                          <div>
                            <h4 className="font-bold text-sm tracking-tight line-clamp-2">{artifact.file_name}</h4>
                            <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mt-2">
                              {artifact.created_at ? formatDate(artifact.created_at) : "Recently uploaded"}
                            </p>
                          </div>
                          <span className="material-symbols-outlined text-indigo-400 text-sm">verified</span>
                        </div>
                      </button>

                      <div className="absolute top-3 right-3 z-20">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setMenuOpenForArtifact(menuOpenForArtifact === artifact.id ? null : artifact.id);
                          }}
                          disabled={deletingArtifactId === artifact.id || replacingArtifactId === artifact.id}
                          className="w-8 h-8 rounded-full bg-black/20 hover:bg-black/40 text-white flex items-center justify-center backdrop-blur-md transition-all disabled:opacity-50"
                        >
                          <span className="material-symbols-outlined text-[18px]">more_vert</span>
                        </button>

                        {menuOpenForArtifact === artifact.id && (
                          <>
                            <div className="fixed inset-0 z-40" onClick={(e) => { e.stopPropagation(); setMenuOpenForArtifact(null); }} />
                            <div className="absolute right-0 mt-2 w-36 rounded-2xl bg-surface-container-high border border-outline-variant/10 shadow-xl overflow-hidden z-50 flex flex-col py-1 animate-fade-in-up origin-top-right">
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setReplacingArtifactId(artifact.id);
                                  replaceInputRef.current?.click();
                                  setMenuOpenForArtifact(null);
                                }}
                                className="w-full text-left px-4 py-2.5 text-sm font-medium text-on-surface hover:bg-surface-container-highest transition-colors flex items-center gap-2"
                              >
                                <span className="material-symbols-outlined text-[16px]">edit</span>
                                Replace
                              </button>
                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setArtifactToDelete(artifact);
                                  setMenuOpenForArtifact(null);
                                }}
                                className="w-full text-left px-4 py-2.5 text-sm font-bold text-red-400 hover:bg-red-500/10 transition-colors flex items-center gap-2"
                              >
                                <span className="material-symbols-outlined text-[16px]">delete</span>
                                Delete
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  ))}

                  <div
                    onClick={() => proofInputRef.current?.click()}
                    className="lift-card rounded-3xl border-2 border-dashed border-outline-variant/12 dark:border-transparent bg-surface-container-low/40 hover:border-indigo-500/40 hover:bg-indigo-500/5 flex flex-col items-center justify-center p-6 text-center cursor-pointer transition-all min-h-[220px] group shadow-inner"
                  >
                    <div className="w-16 h-16 rounded-full bg-surface-container flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                      <span className="material-symbols-outlined text-4xl text-on-surface-variant group-hover:text-indigo-400 transition-colors">cloud_upload</span>
                    </div>
                    <span className="font-bold text-sm tracking-tight text-on-surface">Upload Credential</span>
                    <span className="text-[10px] text-on-surface-variant mt-2 font-black uppercase tracking-tighter">PDF or Image</span>
                  </div>
                </>
              ) : (
                <ListSkeleton count={3} />
              )}
            </div>
          </section>
          ) : null}
        </div>
      </div>

      {selectedArtifact ? (
        <div className="fixed inset-0 z-[120] bg-black/90 backdrop-blur-xl flex items-center justify-center p-8 transition-all animate-fade-in">
          <div className="absolute inset-0" onClick={() => setSelectedArtifact(null)} />
          <div className="relative w-full max-w-3xl clay-card rounded-[40px] border border-outline-variant/12 dark:border-transparent p-8 flex flex-col shadow-[0_0_100px_rgba(0,0,0,1)]">
            <div className="flex justify-between items-center mb-6">
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-indigo-400">verified</span>
                <h2 className="text-xl font-bold tracking-tight text-on-surface">{selectedArtifact.file_name}</h2>
              </div>
              <button onClick={() => setSelectedArtifact(null)} className="w-12 h-12 flex items-center justify-center bg-surface-container hover:bg-surface-container-high rounded-full transition-all text-on-surface hover:scale-110 active:scale-90">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="rounded-[28px] border border-outline-variant/12 dark:border-transparent bg-surface-container-low p-8 text-on-surface-variant overflow-y-auto max-h-[60vh]">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant mb-2">Type</p>
                  <p className="text-sm font-bold text-on-surface">{toTitleCase(selectedArtifact.file_type)}</p>
                </div>
                <div>
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-on-surface-variant mb-2">Uploaded</p>
                  <p className="text-sm font-bold text-on-surface">{selectedArtifact.created_at ? formatDate(selectedArtifact.created_at) : "Recently uploaded"}</p>
                </div>
                
                <div className="md:col-span-2 pt-4 border-t border-outline-variant/12">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary mb-3">Extracted derivations</p>
                  <div className="space-y-4">
                    <div className="rounded-2xl bg-surface p-4 border border-outline-variant/10 shadow-inner">
                      <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Detected skills</p>
                      <div className="flex flex-wrap gap-2">
                        {/* We could fetch this from hidden_skills or similar. For now, we show a loading message if parsing or a fallback */}
                        {selectedArtifact.extracted_text ? (
                          <p className="text-[11px] leading-relaxed italic">
                            Evidence from this artifact is feeding your personalized RAG Copilot and skill discovery queue.
                          </p>
                        ) : (
                          <p className="text-xs italic text-on-surface-variant/60">No skills derived yet. Processing might still be in progress.</p>
                        )}
                      </div>
                    </div>
                    
                    <div className="rounded-2xl bg-surface p-4 border border-outline-variant/10 shadow-inner">
                      <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Extracted snapshot</p>
                      <p className="text-sm leading-6 line-clamp-4">
                        {selectedArtifact.extracted_text || "Text extraction pending or unavailable for this file type."}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {artifactToDelete ? (
        <div className="fixed inset-0 z-[130] bg-black/60 backdrop-blur-sm flex items-center justify-center p-8 transition-all animate-fade-in">
          <div className="absolute inset-0" onClick={() => setArtifactToDelete(null)} />
          <div className="relative w-full max-w-md clay-card rounded-[32px] p-8 flex flex-col shadow-2xl border border-outline-variant/10">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center shrink-0">
                <span className="material-symbols-outlined text-red-500">warning</span>
              </div>
              <div>
                <h3 className="text-lg font-bold text-on-surface">Delete Credential</h3>
                <p className="text-sm font-medium text-on-surface-variant truncate max-w-[250px]">{artifactToDelete.file_name}</p>
              </div>
            </div>
            <p className="text-sm text-on-surface-variant mb-8 leading-relaxed">
              Are you sure you want to delete this file? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setArtifactToDelete(null)}
                className="px-6 py-2.5 rounded-full text-sm font-bold text-on-surface hover:bg-surface-container-high transition-all"
              >
                Cancel
              </button>
              <button
                onClick={confirmDelete}
                className="px-6 py-2.5 rounded-full text-sm font-bold bg-red-500 text-white shadow-lg shadow-red-500/20 hover:bg-red-600 transition-all flex items-center gap-2"
              >
                <span className="material-symbols-outlined text-[18px]">delete</span>
                Delete
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
