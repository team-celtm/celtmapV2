"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { AnimatePresence, motion as Motion } from "framer-motion";
import { ApiError, apiFetch, apiFetchBlob } from "@/lib/api";
import type {
  ArtifactRead,
  CareerAspirationRead,
  CareerRecommendationResponse,
  CareerRoleOption,
  DashboardSummary,
  CareerLink,
  ProfileRead,
  ProfileLinkEvidence,
  ProfileLinkValidationResponse,
  RoleFitRead,
  SkillRead,
  UserPreferenceRead,
} from "@/lib/celtm";
import { formatDate, toTitleCase } from "@/lib/celtm";
import { FormSkeleton, ListSkeleton } from "@/components/common/Skeletons";
import { resolveStorageAssetUrl } from "@/lib/storage";
import { useAuth } from "@/contexts/AuthContext";
import AppIcon from "@/components/AppIcon";
import {
  CareerRecommendationPanel,
  DraftPersonalityPanel,
  type DraftPersonalityKey,
  type DraftPersonalityState,
  initialDraftPersonality,
  normalizeDraftPersonality,
} from "@/components/career/DigitalPersonality";
import CareerRoleInput from "@/components/career/CareerRoleInput";

interface ProfileMetadata {
  bio?: string;
  location?: string;
  target_industry?: string;
  career_links?: CareerLink[];
  career_link_evidence?: ProfileLinkEvidence;
  draft_personality?: unknown;
}

type ExtraCareerLink = CareerLink & { id: string };

type SettingsTabKey = "profile" | "career" | "passport" | "notifications" | "credentials";

const SETTINGS_TABS: Array<{ key: SettingsTabKey; icon: string; label: string }> = [
  { key: "profile", icon: "person", label: "Personal Profile" },
  { key: "career", icon: "psychology", label: "Career Personality" },
  { key: "passport", icon: "badge", label: "Passport Export" },
  { key: "notifications", icon: "notifications_active", label: "Notifications" },
  { key: "credentials", icon: "workspace_premium", label: "Credentials" },
];

interface CredentialEvaluation {
  score?: number;
  verdict?: string;
  issuer?: string;
  readiness_delta?: number;
  detected_skills?: unknown[];
  reasons?: unknown[];
  risks?: unknown[];
  recommendations?: unknown[];
}

function sanitizeFileName(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "celtm-passport";
}

function credentialEvaluation(artifact: ArtifactRead | null): CredentialEvaluation | null {
  const value = artifact?.metadata?.credential_evaluation;
  return value && typeof value === "object" ? (value as CredentialEvaluation) : null;
}

function stringList(values: unknown[] | undefined): string[] {
  return (values ?? []).map((item) => String(item)).filter(Boolean);
}

function careerLinksFromMetadata(metadata: ProfileMetadata): CareerLink[] {
  return Array.isArray(metadata.career_links)
    ? metadata.career_links.filter((item) => item && typeof item.url === "string")
    : [];
}

function firstLinkByType(links: CareerLink[], type: string): string {
  return links.find((item) => item.type === type)?.url ?? "";
}

function extraLinksFromMetadata(links: CareerLink[]): ExtraCareerLink[] {
  return links
    .filter((item) => !["linkedin", "github", "portfolio"].includes(item.type))
    .map((item, index) => ({
      id: `${Date.now()}-${index}`,
      label: item.label || "Additional link",
      url: item.url,
      type: item.type || "portfolio",
    }));
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
    linkedInUrl: "",
    githubUrl: "",
    portfolioUrl: "",
    extraLinks: [] as ExtraCareerLink[],
  });
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactRead | null>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isReadinessLoading, setIsReadinessLoading] = useState(false);
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
  const [readinessStateError, setReadinessStateError] = useState<string | null>(null);
  const [linkEvidence, setLinkEvidence] = useState<ProfileLinkEvidence | null>(null);
  const [draftPersonality, setDraftPersonality] = useState<DraftPersonalityState>(initialDraftPersonality);
  const [careerRecommendations, setCareerRecommendations] = useState<CareerRecommendationResponse | null>(null);
  const [roleOptions, setRoleOptions] = useState<CareerRoleOption[]>([]);
  const [isSavingDraftPersonality, setIsSavingDraftPersonality] = useState(false);
  const [careerActionRole, setCareerActionRole] = useState<string | null>(null);
  const [activeRoleAction, setActiveRoleAction] = useState<string | null>(null);
  const [isAnalyzingAllPaths, setIsAnalyzingAllPaths] = useState(false);
  const [showPersonalityCreated, setShowPersonalityCreated] = useState(false);

  const profileInputRef = useRef<HTMLInputElement>(null);
  const proofInputRef = useRef<HTMLInputElement>(null);
  const replaceInputRef = useRef<HTMLInputElement>(null);
  const selectedEvaluation = credentialEvaluation(selectedArtifact);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const requestedTab = new URLSearchParams(window.location.search).get("tab");
    if (requestedTab && SETTINGS_TABS.some((tab) => tab.key === requestedTab)) {
      setActiveTab(requestedTab as SettingsTabKey);
    }
  }, []);

  const refreshReadinessState = async () => {
    setIsReadinessLoading(true);
    setReadinessStateError(null);
    const [artifactsResult, summaryResult, roleFitResult, skillsResult] = await Promise.allSettled([
      apiFetch<ArtifactRead[]>("/profile/me/artifacts"),
      apiFetch<DashboardSummary>("/dashboard/summary"),
      apiFetch<RoleFitRead>("/skills/me/role-fit"),
      apiFetch<SkillRead[]>("/skills/me"),
    ]);
    const failures: string[] = [];
    if (artifactsResult.status === "fulfilled") {
      setArtifacts(artifactsResult.value);
      setSelectedArtifact((current) => current ? artifactsResult.value.find((artifact) => artifact.id === current.id) ?? null : null);
    } else {
      failures.push("credentials");
    }
    if (summaryResult.status === "fulfilled") {
      setSummary(summaryResult.value);
    } else {
      failures.push("dashboard summary");
    }
    if (roleFitResult.status === "fulfilled") {
      setRoleFit(roleFitResult.value);
    } else {
      failures.push("role fit");
    }
    if (skillsResult.status === "fulfilled") {
      setSkills(skillsResult.value);
    } else {
      failures.push("skills");
    }
    setReadinessStateError(failures.length ? `${failures.join(", ")} not available from the backend right now.` : null);
    setIsReadinessLoading(false);
  };

  useEffect(() => {
    let isMounted = true;

    const loadSettings = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const [profilePayload, settingsPayload, rolePayload] = await Promise.all([
          apiFetch<ProfileRead>("/profile/me"),
          apiFetch<UserPreferenceRead>("/settings/me"),
          apiFetch<CareerRoleOption[]>("/career-roles"),
        ]);

        if (!isMounted) {
          return;
        }

        const metadata = (profilePayload.metadata ?? {}) as ProfileMetadata;
        const careerLinks = careerLinksFromMetadata(metadata);
        setProfile(profilePayload);
        setSettings(settingsPayload);
        setRoleOptions(rolePayload);
        setLinkEvidence(metadata.career_link_evidence ?? null);
        setDraftPersonality(normalizeDraftPersonality(metadata.draft_personality));
        setForm({
          fullName: profilePayload.full_name ?? "",
          headline: profilePayload.headline ?? "",
          focusRole: profilePayload.focus_role ?? "",
          weeklyGoal: profilePayload.weekly_goal ?? "",
          bio: metadata.bio ?? "",
          location: metadata.location ?? "",
          targetIndustry: metadata.target_industry ?? "",
          linkedInUrl: firstLinkByType(careerLinks, "linkedin"),
          githubUrl: firstLinkByType(careerLinks, "github"),
          portfolioUrl: firstLinkByType(careerLinks, "portfolio"),
          extraLinks: extraLinksFromMetadata(careerLinks),
        });
        void refreshReadinessState();
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
      await refreshReadinessState();
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
      await refreshReadinessState();
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
      await refreshReadinessState();
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

  const buildCareerLinks = (): CareerLink[] => {
    return [
      { label: "LinkedIn", url: form.linkedInUrl.trim(), type: "linkedin" },
      { label: "GitHub", url: form.githubUrl.trim(), type: "github" },
      { label: "Portfolio", url: form.portfolioUrl.trim(), type: "portfolio" },
      ...form.extraLinks.map((item) => ({
        label: item.label.trim() || "Additional link",
        url: item.url.trim(),
        type: item.type.trim() || "portfolio",
      })),
    ].filter((item) => item.url);
  };

  const addExtraLink = () => {
    setForm((current) => ({
      ...current,
      extraLinks: [
        ...current.extraLinks,
        { id: `${Date.now()}`, label: "Additional link", url: "", type: "portfolio" },
      ],
    }));
  };

  const updateExtraLink = (id: string, patch: Partial<ExtraCareerLink>) => {
    setForm((current) => ({
      ...current,
      extraLinks: current.extraLinks.map((item) => item.id === id ? { ...item, ...patch } : item),
    }));
  };

  const removeExtraLink = (id: string) => {
    setForm((current) => ({
      ...current,
      extraLinks: current.extraLinks.filter((item) => item.id !== id),
    }));
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);
      setSaveSuccess(false);
      setError(null);
      const careerLinks = buildCareerLinks();

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
            career_links: careerLinks,
            career_link_evidence: careerLinks.length ? (profile?.metadata?.career_link_evidence ?? null) : null,
          },
        }),
      });

      const updatedSettings = await apiFetch<UserPreferenceRead>("/settings/me", {
        method: "PATCH",
        body: JSON.stringify({
          folio_focus: form.focusRole,
        }),
      });

      let savedProfile = updatedProfile;
      if (careerLinks.length > 0) {
        const validation = await apiFetch<ProfileLinkValidationResponse>("/profile/me/evidence-links", {
          method: "POST",
          body: JSON.stringify({ links: careerLinks }),
        });
        savedProfile = validation.profile;
        setLinkEvidence(validation.evidence);
        await refreshReadinessState();
      } else {
        setLinkEvidence(null);
        await refreshReadinessState();
      }

      setProfile(savedProfile);
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

  const toggleDraftOption = (key: DraftPersonalityKey, value: string) => {
    setDraftPersonality((current) => {
      const values = current[key];
      return {
        ...current,
        [key]: values.includes(value) ? values.filter((item) => item !== value) : [...values, value],
      };
    });
  };

  const saveDraftPersonality = async () => {
    try {
      setIsSavingDraftPersonality(true);
      setError(null);
      const payload = await apiFetch<CareerRecommendationResponse>("/career-recommendations/draft-personality", {
        method: "POST",
        body: JSON.stringify(draftPersonality),
      });
      setCareerRecommendations(payload);
      setProfile((current) => current
        ? {
            ...current,
            metadata: {
              ...(current.metadata ?? {}),
              draft_personality: payload.draft_personality ?? draftPersonality,
            },
          }
        : current);
      setShowPersonalityCreated(true);
      await refreshProfile();
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Could not build the draft CELTM personality.";
      setError(message);
    } finally {
      setIsSavingDraftPersonality(false);
    }
  };

  const openCareerPath = async (role: string) => {
    try {
      setCareerActionRole(role);
      setError(null);
      const created = await apiFetch<CareerAspirationRead>("/career-aspirations", {
        method: "POST",
        body: JSON.stringify({ desired_role: role }),
      });
      window.location.href = `/career-aim?selected=${encodeURIComponent(created.id)}`;
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Could not analyze this career path.";
      setError(message);
      setCareerActionRole(null);
    }
  };

  const setActiveCareerAim = async (role: string) => {
    try {
      setActiveRoleAction(role);
      setError(null);
      const updatedProfile = await apiFetch<ProfileRead>("/profile/me", {
        method: "PATCH",
        body: JSON.stringify({
          focus_role: role,
          metadata: profile?.metadata ?? {},
        }),
      });
      const updatedSettings = await apiFetch<UserPreferenceRead>("/settings/me", {
        method: "PATCH",
        body: JSON.stringify({
          folio_focus: role,
        }),
      });
      setProfile(updatedProfile);
      setSettings(updatedSettings);
      setForm((current) => ({ ...current, focusRole: role }));
      setSaveSuccess(true);
      await refreshProfile();
      window.setTimeout(() => setSaveSuccess(false), 3000);
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Could not set this role as the active career aim.";
      setError(message);
    } finally {
      setActiveRoleAction(null);
    }
  };

  const analyzeAllCareerPaths = async () => {
    const roles = (careerRecommendations?.recommendations ?? []).map((item) => item.role).slice(0, 3);
    if (!roles.length) {
      return;
    }
    try {
      setIsAnalyzingAllPaths(true);
      setError(null);
      const created = await apiFetch<CareerAspirationRead[]>("/career-aspirations/recommended", {
        method: "POST",
        body: JSON.stringify({ desired_roles: roles }),
      });
      const first = created[0];
      window.location.href = first ? `/career-aim?selected=${encodeURIComponent(first.id)}` : "/career-aim";
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Could not analyze all recommended paths.";
      setError(message);
      setIsAnalyzingAllPaths(false);
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
  const isArtifactsLoaded = !isReadinessLoading;

  return (
    <div className="w-full max-w-[1520px] mx-auto space-y-6 animate-fade-in pb-12">
      {error ? (
        <div className="rounded-2xl border border-red-500/20 bg-red-500/10 px-5 py-4 text-sm text-red-400">
          {error}
        </div>
      ) : null}
      {isReadinessLoading ? (
        <div className="rounded-2xl border border-primary/15 bg-primary/5 px-5 py-3 text-xs font-black uppercase tracking-[0.18em] text-primary">
          Syncing readiness evidence...
        </div>
      ) : null}
      {readinessStateError ? (
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-5 py-4 text-sm font-semibold text-amber-700 dark:text-amber-300">
          {readinessStateError}
        </div>
      ) : null}

      <div className="grid grid-cols-12 gap-8">
        <aside className="col-span-12 lg:col-span-3">
          <div className="flex flex-col gap-2">
            <h1 className="text-3xl font-extrabold tracking-tight text-on-surface mb-6">Settings</h1>
            {SETTINGS_TABS.map((item) => {
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
                  <AppIcon name={item.icon} className="h-5 w-5" />
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
                  <Image
                    alt="User Avatar"
                    className="w-full h-full object-cover"
                    src={currentAvatar}
                    width={128}
                    height={128}
                    unoptimized
                    onError={(event) => {
                      event.currentTarget.onerror = null;
                      event.currentTarget.src = "https://ui-avatars.com/api/?name=CELTM+User&background=6366f1&color=fff";
                    }}
                  />
                  <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <AppIcon name={uploadingAvatar ? "sync" : "add_a_photo"} className={`h-8 w-8 text-white ${uploadingAvatar ? "animate-spin" : ""}`} />
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
                      <CareerRoleInput
                        label="Focus Role"
                        value={form.focusRole}
                        onChange={(value) => setForm((current) => ({ ...current, focusRole: value }))}
                        placeholder="Type any focus role"
                        options={roleOptions}
                        inputClassName="border-outline-variant/12 bg-surface-container-low px-5 py-3 font-bold"
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

                  <div className="rounded-[28px] border border-outline-variant/12 bg-surface-container-low/70 p-5">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary">Career evidence links</p>
                        <p className="mt-2 text-sm font-semibold leading-6 text-on-surface-variant">
                          Add LinkedIn, GitHub, portfolio, certificate, or project links. CELTM validates these links and includes the crawled evidence in readiness.
                        </p>
                      </div>
                      {linkEvidence ? (
                        <span className="rounded-full bg-emerald-500/10 px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-emerald-600">
                          Link score {Math.round(Number(linkEvidence.score ?? 0))}%
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-5 grid gap-4 md:grid-cols-3">
                      <div className="space-y-2">
                        <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">LinkedIn</label>
                        <input
                          type="url"
                          placeholder="https://linkedin.com/in/..."
                          className="w-full rounded-2xl border border-outline-variant/12 bg-surface px-4 py-3 text-sm font-bold text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/40"
                          value={form.linkedInUrl}
                          onChange={(event) => setForm((current) => ({ ...current, linkedInUrl: event.target.value }))}
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">GitHub</label>
                        <input
                          type="url"
                          placeholder="https://github.com/..."
                          className="w-full rounded-2xl border border-outline-variant/12 bg-surface px-4 py-3 text-sm font-bold text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/40"
                          value={form.githubUrl}
                          onChange={(event) => setForm((current) => ({ ...current, githubUrl: event.target.value }))}
                        />
                      </div>
                      <div className="space-y-2">
                        <label className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Portfolio</label>
                        <input
                          type="url"
                          placeholder="https://your-site.com"
                          className="w-full rounded-2xl border border-outline-variant/12 bg-surface px-4 py-3 text-sm font-bold text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/40"
                          value={form.portfolioUrl}
                          onChange={(event) => setForm((current) => ({ ...current, portfolioUrl: event.target.value }))}
                        />
                      </div>
                    </div>

                    <div className="mt-4 space-y-3">
                      {form.extraLinks.map((item) => (
                        <div key={item.id} className="grid gap-3 rounded-2xl bg-surface p-3 md:grid-cols-[1fr_1fr_1fr_auto]">
                          <input
                            value={item.label}
                            onChange={(event) => updateExtraLink(item.id, { label: event.target.value })}
                            placeholder="Label"
                            className="rounded-xl border border-outline-variant/12 bg-surface-container-low px-3 py-2 text-sm font-bold text-on-surface"
                          />
                          <input
                            value={item.type}
                            onChange={(event) => updateExtraLink(item.id, { type: event.target.value })}
                            placeholder="portfolio, certificate, project"
                            className="rounded-xl border border-outline-variant/12 bg-surface-container-low px-3 py-2 text-sm font-bold text-on-surface"
                          />
                          <input
                            value={item.url}
                            onChange={(event) => updateExtraLink(item.id, { url: event.target.value })}
                            placeholder="https://..."
                            className="rounded-xl border border-outline-variant/12 bg-surface-container-low px-3 py-2 text-sm font-bold text-on-surface"
                          />
                          <button
                            type="button"
                            onClick={() => removeExtraLink(item.id)}
                            className="rounded-xl bg-red-500/10 px-3 py-2 text-[10px] font-black uppercase tracking-widest text-red-500"
                          >
                            Remove
                          </button>
                        </div>
                      ))}
                      <button
                        type="button"
                        onClick={addExtraLink}
                        className="rounded-2xl bg-surface px-4 py-2 text-[10px] font-black uppercase tracking-[0.18em] text-primary"
                      >
                        Add another link
                      </button>
                    </div>

                    {linkEvidence?.links?.length ? (
                      <div className="mt-4 grid gap-2">
                        {linkEvidence.links.slice(0, 4).map((item) => (
                          <div key={`${item.type}-${item.url}`} className="flex flex-col gap-1 rounded-2xl bg-surface px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                            <p className="text-xs font-black text-on-surface">{item.label || item.type}</p>
                            <p className={`text-[10px] font-black uppercase tracking-widest ${item.reachable ? "text-emerald-600" : "text-red-500"}`}>
                              {item.reachable ? `Validated ${Math.round(Number(item.score ?? 0))}%` : "Not reachable"}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : null}
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
                <AppIcon name={isSaving ? "sync" : "verified_user"} className={`h-4 w-4 ${isSaving ? "animate-spin" : ""}`} />
                {isSaving ? "Saving..." : "Update Profile"}
              </button>
            </div>
          </section>
          ) : null}

          {activeTab === "career" ? (
            <div className="space-y-6">
              <section className="clay-card rounded-[32px] p-8">
                <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                  <div>
                    <p className="text-[10px] font-black uppercase tracking-[0.24em] text-primary">Career aim without resume</p>
                    <h3 className="mt-2 text-2xl font-black tracking-tight text-on-surface">Draft CELTM personality</h3>
                    <p className="mt-2 max-w-3xl text-sm font-semibold leading-6 text-on-surface-variant">
                      Use this only when there is no resume yet. CELTM stores it as temporary evidence and replaces it with stronger resume, link, credential, and assessment signals as they are added.
                    </p>
                  </div>
                  <span className="rounded-full bg-surface-container-low px-4 py-2 text-[10px] font-black uppercase tracking-widest text-on-surface-variant">
                    Focus role: {form.focusRole || "Not set"}
                  </span>
                </div>
              </section>

              {isProfileLoaded ? (
                <DraftPersonalityPanel
                  draft={draftPersonality}
                  isSaving={isSavingDraftPersonality}
                  needsAssessment={careerRecommendations?.needs_assessment_for_skills ?? true}
                  recommendations={careerRecommendations?.recommendations ?? []}
                  onToggle={toggleDraftOption}
                  onChange={(patch) => setDraftPersonality((current) => ({ ...current, ...patch }))}
                  onSave={() => void saveDraftPersonality()}
                />
              ) : (
                <FormSkeleton />
              )}

              {careerRecommendations ? (
                <CareerRecommendationPanel
                  payload={careerRecommendations}
                  activeTargetRole={form.focusRole}
                  actionRole={careerActionRole}
                  activeRoleAction={activeRoleAction}
                  isAnalyzingAll={isAnalyzingAllPaths}
                  onSelectPath={(role) => void openCareerPath(role)}
                  onSetActiveRole={(role) => void setActiveCareerAim(role)}
                  onAnalyzeAll={() => void analyzeAllCareerPaths()}
                />
              ) : null}
            </div>
          ) : null}

          {activeTab === "passport" ? (
          <section className="clay-card rounded-[32px] p-8 relative overflow-hidden group">
            <div className="absolute -right-12 -top-12 w-48 h-48 bg-gradient-to-br from-indigo-500/10 to-purple-500/10 rounded-full blur-3xl group-hover:scale-150 transition-transform duration-700" />
            <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
              <div className="flex items-start gap-5">
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 shrink-0">
                  <AppIcon name="verified" className="h-8 w-8 text-white" />
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
                    <div className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors duration-300 ease-in-out ${item.enabled ? 'bg-primary' : 'bg-surface-container-highest'}`}>
                      <span className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-transform duration-300 ease-in-out ${item.enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                    </div>
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
                <AppIcon name={uploadingArtifact ? "sync" : "add_circle"} className={`h-4 w-4 ${uploadingArtifact ? "animate-spin" : ""}`} />
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
                          <AppIcon
                            name={artifact.file_name.toLowerCase().endsWith(".pdf") ? "description" : "image"}
                            className="h-12 w-12 text-primary/70"
                          />
                          {(deletingArtifactId === artifact.id || replacingArtifactId === artifact.id) && (
                            <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                              <AppIcon name="sync" className="h-8 w-8 animate-spin text-white" />
                            </div>
                          )}
                        </div>
                        <div className="flex items-start justify-between px-1 gap-3">
                          <div>
                            <h4 className="font-bold text-sm tracking-tight line-clamp-2">{artifact.file_name}</h4>
                            <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mt-2">
                              {artifact.created_at ? formatDate(artifact.created_at) : "Recently uploaded"}
                            </p>
                            {credentialEvaluation(artifact) ? (
                              <p className="mt-2 text-[11px] font-black text-primary">
                                Credential score {Math.round(Number(credentialEvaluation(artifact)?.score ?? 0))}% - {toTitleCase(String(credentialEvaluation(artifact)?.verdict ?? "evaluated"))}
                              </p>
                            ) : artifact.metadata?.evaluation_status === "pending" ? (
                              <p className="mt-2 text-[11px] font-black text-amber-500">Evaluation pending</p>
                            ) : null}
                          </div>
                          <AppIcon name="verified" className="h-4 w-4 text-indigo-400" />
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
                          <AppIcon name="more_vert" className="h-4 w-4" />
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
                                <AppIcon name="edit" className="h-4 w-4" />
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
                                <AppIcon name="delete" className="h-4 w-4" />
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
                      <AppIcon name="cloud_upload" className="h-10 w-10 text-on-surface-variant transition-colors group-hover:text-indigo-400" />
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
                <AppIcon name="verified" className="h-5 w-5 text-indigo-400" />
                <h2 className="text-xl font-bold tracking-tight text-on-surface">{selectedArtifact.file_name}</h2>
              </div>
              <button onClick={() => setSelectedArtifact(null)} className="w-12 h-12 flex items-center justify-center bg-surface-container hover:bg-surface-container-high rounded-full transition-all text-on-surface hover:scale-110 active:scale-90">
                <AppIcon name="close" className="h-5 w-5" />
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

                {selectedEvaluation ? (
                  <div className="md:col-span-2 rounded-3xl border border-primary/10 bg-primary/5 p-5">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary mb-2">AI credential evaluation</p>
                        <p className="text-sm font-bold text-on-surface">
                          {toTitleCase(String(selectedEvaluation.verdict ?? "evaluated"))} credential from {selectedEvaluation.issuer || "unknown issuer"}
                        </p>
                      </div>
                      <div className="rounded-2xl bg-surface px-4 py-3 text-center">
                        <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant">Score</p>
                        <p className="text-2xl font-black text-primary">{Math.round(Number(selectedEvaluation.score ?? 0))}%</p>
                      </div>
                    </div>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      <div>
                        <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Detected skills</p>
                        <div className="flex flex-wrap gap-2">
                          {stringList(selectedEvaluation.detected_skills).map((skill) => (
                            <span key={skill} className="rounded-full bg-surface px-3 py-1 text-[11px] font-bold text-on-surface">{skill}</span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Readiness impact</p>
                        <p className="text-sm leading-6 text-on-surface-variant">
                          Directional delta: {Number(selectedEvaluation.readiness_delta ?? 0) >= 0 ? "+" : ""}{Number(selectedEvaluation.readiness_delta ?? 0).toFixed(1)} before product weighting.
                        </p>
                      </div>
                    </div>
                    {stringList(selectedEvaluation.reasons).length ? (
                      <ul className="mt-4 space-y-2 text-sm leading-6 text-on-surface-variant">
                        {stringList(selectedEvaluation.reasons).slice(0, 4).map((reason) => <li key={reason}>- {reason}</li>)}
                      </ul>
                    ) : null}
                  </div>
                ) : null}
                
                <div className="md:col-span-2 pt-4 border-t border-outline-variant/12">
                  <p className="text-[10px] font-black uppercase tracking-[0.2em] text-primary mb-3">Extracted derivations</p>
                  <div className="space-y-4">
                    <div className="rounded-2xl bg-surface p-4 border border-outline-variant/10 shadow-inner">
                      <p className="text-[10px] font-black uppercase tracking-widest text-on-surface-variant mb-2">Detected skills</p>
                      <div className="flex flex-wrap gap-2">
                        {/* We could fetch this from hidden_skills or similar. For now, we show a loading message if parsing or a fallback */}
                        {selectedArtifact.extracted_text ? (
                          <p className="text-[11px] leading-relaxed italic">
                            Evidence from this artifact feeds lightweight skill discovery and passport reporting.
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

      <AnimatePresence>
        {showPersonalityCreated ? (
          <Motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[140] flex items-center justify-center bg-black/50 px-4 backdrop-blur-sm"
            role="dialog"
            aria-modal="true"
            aria-label="Personality created"
          >
            <Motion.div
              initial={{ opacity: 0, y: 24, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.98 }}
              className="w-full max-w-md rounded-[32px] bg-surface p-7 shadow-2xl"
            >
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600">
                <AppIcon name="check_circle" className="h-8 w-8" />
              </div>
              <h2 className="mt-5 text-center text-2xl font-black tracking-tight text-on-surface">Personality created</h2>
              <p className="mt-3 text-center text-sm font-semibold leading-6 text-on-surface-variant">
                Your draft digital CELTM personality is saved. The AI predicted top 3 fits are available in this Settings career section.
              </p>
              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setShowPersonalityCreated(false)}
                  className="rounded-2xl bg-primary px-5 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-white"
                >
                  View fits
                </button>
                <button
                  type="button"
                  onClick={() => setShowPersonalityCreated(false)}
                  className="rounded-2xl bg-surface-container-high px-5 py-3 text-[11px] font-black uppercase tracking-[0.18em] text-on-surface"
                >
                  Close
                </button>
              </div>
            </Motion.div>
          </Motion.div>
        ) : null}
      </AnimatePresence>

      {artifactToDelete ? (
        <div className="fixed inset-0 z-[130] bg-black/60 backdrop-blur-sm flex items-center justify-center p-8 transition-all animate-fade-in">
          <div className="absolute inset-0" onClick={() => setArtifactToDelete(null)} />
          <div className="relative w-full max-w-md clay-card rounded-[32px] p-8 flex flex-col shadow-2xl border border-outline-variant/10">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center shrink-0">
                <AppIcon name="warning" className="h-5 w-5 text-red-500" />
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
                <AppIcon name="delete" className="h-4 w-4" />
                Delete
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
