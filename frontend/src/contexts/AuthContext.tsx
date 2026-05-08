"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { apiFetch, setApiAuthSession } from "../lib/api";
import { resolveStorageAssetUrl } from "../lib/storage";
import { assertSupabaseConfigured, supabase } from "../lib/supabase";

const DEFAULT_AVATAR = "https://ui-avatars.com/api/?name=CELTM+User&background=6366f1&color=fff";

interface UserProfileAssets {
  resumeName: string;
  primaryCertificateName: string;
  supportingCertificateNames: string[];
}

interface BackendProfileMetadata {
  portfolio_score?: number;
  profile_assets?: Partial<UserProfileAssets>;
  self_reported_skills?: string[];
  has_completed_onboarding?: boolean;
  has_completed_placement?: boolean;
  bio?: string;
  location?: string;
  target_industry?: string;
}

interface BackendProfile {
  id: string;
  email?: string | null;
  full_name?: string | null;
  headline?: string | null;
  focus_role?: string | null;
  weekly_goal?: string | null;
  avatar_url?: string | null;
  metadata?: BackendProfileMetadata | null;
}

interface SessionUserMetadata {
  full_name?: string;
  name?: string;
  has_completed_onboarding?: boolean;
  [key: string]: unknown;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: string;
  focusRole: string;
  weeklyGoal: string;
  portfolioScore: number;
  avatar: string;
  profileAssets: UserProfileAssets;
  selfReportedSkills: string[];
  hasCompletedOnboarding: boolean;
  hasCompletedPlacement: boolean;
}

interface SignInPayload {
  email: string;
  password: string;
}

interface SignUpPayload extends SignInPayload {
  name: string;
  emailRedirectTo?: string;
}

interface SignUpResult {
  requiresEmailConfirmation: boolean;
  sessionEstablished: boolean;
  user?: UserProfile | null;
}

interface AuthContextType {
  user: UserProfile | null;
  session: Session | null;
  signIn: (payload: SignInPayload) => Promise<UserProfile | null>;
  signUp: (payload: SignUpPayload) => Promise<SignUpResult>;
  logout: () => Promise<void>;
  updateUser: (updates: Partial<UserProfile>) => Promise<void>;
  completeOnboarding: (updates?: Partial<UserProfile>) => Promise<void>;
  refreshProfile: () => Promise<void>;
  isLoading: boolean;
}

const defaultProfileAssets: UserProfileAssets = {
  resumeName: "",
  primaryCertificateName: "",
  supportingCertificateNames: [],
};

const defaultProfileValues = {
  role: "",
  focusRole: "",
  weeklyGoal: "",
  portfolioScore: 0,
  avatar: DEFAULT_AVATAR,
  selfReportedSkills: [],
  hasCompletedOnboarding: false,
  hasCompletedPlacement: false,
};

const AuthContext = createContext<AuthContextType>({} as AuthContextType);

function getSessionUserMetadata(session: Session | null): SessionUserMetadata {
  const metadata = session?.user.user_metadata;
  if (metadata && typeof metadata === "object" && !Array.isArray(metadata)) {
    return metadata as SessionUserMetadata;
  }

  return {};
}

function getSessionOnboardingStatus(session: Session | null): boolean | null {
  const sessionOnboardingStatus = getSessionUserMetadata(session).has_completed_onboarding;
  return typeof sessionOnboardingStatus === "boolean" ? sessionOnboardingStatus : null;
}

function hasUploadedProfileAssets(assets?: Partial<UserProfileAssets>): boolean {
  if (!assets) {
    return false;
  }

  return Boolean(
    assets.resumeName ||
      assets.primaryCertificateName ||
      (Array.isArray(assets.supportingCertificateNames) && assets.supportingCertificateNames.length > 0),
  );
}

function resolveOnboardingStatus(
  profile: BackendProfile | null,
  metadata: BackendProfileMetadata,
  session: Session | null,
): boolean {
  // 1. If user has core profile fields, they are onboarded
  if (profile?.id) {
    if (profile.headline?.trim() || profile.focus_role?.trim() || profile.weekly_goal?.trim()) return true;
    if (metadata.has_completed_placement) return true;
  }

  // 2. Explicit flag from backend metadata
  if (typeof metadata.has_completed_onboarding === "boolean") {
    return metadata.has_completed_onboarding;
  }

  // 3. Session metadata as secondary source
  const sessionOnboardingStatus = getSessionOnboardingStatus(session);
  if (sessionOnboardingStatus === true) {
    return true;
  }

  return false;
}

function buildUserProfile(
  session: Session,
  profile: BackendProfile | null,
  currentUser: UserProfile | null = null,
): UserProfile {
  const metadata = profile?.metadata ?? {};
  const sessionMetadata = getSessionUserMetadata(session);
  const email = profile?.email ?? session.user.email ?? currentUser?.email ?? "";
  const rawName = profile?.full_name || sessionMetadata.full_name || sessionMetadata.name || currentUser?.name || "";
  const emailPrefix = email.split("@")[0];
  
  // Logic: Prioritize the explicit profile full_name if it exists.
  // Otherwise fallback to session metadata or email prefix.
  const finalName = (profile?.full_name?.trim())
    ? profile.full_name.trim()
    : (rawName && !rawName.includes("@")) 
      ? rawName 
      : (emailPrefix || "CELTM User");


  return {
    id: session.user.id,
    name: finalName,
    email,
    role: profile?.headline ?? currentUser?.role ?? defaultProfileValues.role,
    focusRole: profile?.focus_role ?? currentUser?.focusRole ?? defaultProfileValues.focusRole,
    weeklyGoal: profile?.weekly_goal ?? currentUser?.weeklyGoal ?? defaultProfileValues.weeklyGoal,
    portfolioScore: Number(
      metadata.portfolio_score ?? currentUser?.portfolioScore ?? defaultProfileValues.portfolioScore,
    ),
    avatar: resolveStorageAssetUrl(profile?.avatar_url) ?? currentUser?.avatar ?? defaultProfileValues.avatar,
    profileAssets: {
      ...defaultProfileAssets,
      ...(currentUser?.profileAssets ?? {}),
      ...(metadata.profile_assets ?? {}),
    },
    selfReportedSkills: Array.isArray(metadata.self_reported_skills)
      ? metadata.self_reported_skills
      : currentUser?.selfReportedSkills ?? defaultProfileValues.selfReportedSkills,
    hasCompletedOnboarding: resolveOnboardingStatus(profile, metadata, session),
    hasCompletedPlacement: typeof metadata.has_completed_placement === "boolean"
      ? metadata.has_completed_placement
      : currentUser?.hasCompletedPlacement ?? defaultProfileValues.hasCompletedPlacement,
  };
}

function toProfilePatch(updates: Partial<UserProfile>, currentUser: UserProfile | null) {
  const metadata = {
    portfolio_score: updates.portfolioScore ?? currentUser?.portfolioScore ?? defaultProfileValues.portfolioScore,
    profile_assets: updates.profileAssets ?? currentUser?.profileAssets ?? defaultProfileAssets,
    self_reported_skills:
      updates.selfReportedSkills ?? currentUser?.selfReportedSkills ?? defaultProfileValues.selfReportedSkills,
    has_completed_onboarding:
      updates.hasCompletedOnboarding ??
      currentUser?.hasCompletedOnboarding ??
      defaultProfileValues.hasCompletedOnboarding,
  };

  return {
    full_name: updates.name,
    headline: updates.role,
    focus_role: updates.focusRole,
    weekly_goal: updates.weeklyGoal,
    avatar_url: updates.avatar,
    metadata,
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const userRef = useRef<UserProfile | null>(null);

  useEffect(() => {
    userRef.current = user;
  }, [user]);

  const syncSessionMetadata = useCallback(async (
    activeSession: Session,
    profile: BackendProfile | null,
    nextUser: UserProfile | null,
  ) => {
    const sessionMetadata = getSessionUserMetadata(activeSession);
    const resolvedName =
      profile?.full_name?.trim() || nextUser?.name?.trim() || sessionMetadata.full_name || sessionMetadata.name;
    const resolvedOnboardingStatus = profile
      ? resolveOnboardingStatus(profile, profile.metadata ?? {}, activeSession)
      : nextUser?.hasCompletedOnboarding ?? getSessionOnboardingStatus(activeSession);

    const nextMetadata: SessionUserMetadata = { ...sessionMetadata };
    let shouldSync = false;

    if (resolvedName && sessionMetadata.full_name !== resolvedName) {
      nextMetadata.full_name = resolvedName;
      shouldSync = true;
    }

    if (resolvedName && sessionMetadata.name !== resolvedName) {
      nextMetadata.name = resolvedName;
      shouldSync = true;
    }

    if (
      typeof resolvedOnboardingStatus === "boolean" &&
      sessionMetadata.has_completed_onboarding !== resolvedOnboardingStatus
    ) {
      nextMetadata.has_completed_onboarding = resolvedOnboardingStatus;
      shouldSync = true;
    }

    if (!shouldSync) {
      return;
    }

    try {
      const { error } = await supabase.auth.updateUser({ data: nextMetadata });
      if (error) {
        return;
      }

      const {
        data: { session: refreshedSession },
      } = await supabase.auth.getSession();

      if (!refreshedSession) {
        return;
      }

      setApiAuthSession(refreshedSession);
      setSession(refreshedSession);
    } catch {
      // Ignore metadata sync failures and keep the backend profile as the source of truth.
    }
  }, []);

  const logout = useCallback(async () => {
    assertSupabaseConfigured();
    setApiAuthSession(null);
    await supabase.auth.signOut();
    setUser(null);
    setSession(null);
  }, []);

  const loadProfile = useCallback(async (activeSession: Session | null) => {
    if (!activeSession) {
      setUser(null);
      return null;
    }

    const currentUser =
      userRef.current?.id === activeSession.user.id ? userRef.current : null;

    try {
      const profile = await apiFetch<BackendProfile>("/profile/me");
      const nextUser = buildUserProfile(activeSession, profile, currentUser);
      
      const hasChanged = !currentUser || JSON.stringify(currentUser) !== JSON.stringify(nextUser);
      if (hasChanged) {
        setUser(nextUser);
      }
      
      await syncSessionMetadata(activeSession, profile, nextUser);
      return nextUser;
    } catch (caught) {
      // If we get an Unauthorized error or a network failure during profile load,
      // and we have no currentUser, we should verify if the session is still valid.
      console.error("Profile load failed:", caught);
      
      if (caught instanceof Error && (caught.message.includes("401") || caught.message.includes("Token"))) {
           // If session is explicitly invalid, clear it to prevent loops
           void logout();
           return null;
      }

      const nextUser = currentUser ?? buildUserProfile(activeSession, null);
      setUser(nextUser);
      return nextUser;
    }
  }, [syncSessionMetadata, logout]);

  useEffect(() => {
    let isMounted = true;

    const syncSessionState = async (nextSession: Session | null) => {
      if (!isMounted) {
        return;
      }

      setApiAuthSession(nextSession);
      setSession(nextSession);

      if (!nextSession) {
        setUser(null);
        setIsLoading(false);
        return;
      }

      const isSameUser = userRef.current?.id === nextSession.user.id;
      if (!isSameUser) {
        setIsLoading(true);
      }
      await loadProfile(nextSession);

      if (isMounted && !isSameUser) {
        setIsLoading(false);
      }
    };

    const initialize = async () => {
      try {
        assertSupabaseConfigured();
      } catch {
        if (isMounted) {
          setSession(null);
          setUser(null);
          setIsLoading(false);
        }
        return;
      }

      const {
        data: { session: currentSession },
      } = await supabase.auth.getSession();

      await syncSessionState(currentSession);
    };

    void initialize();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      void syncSessionState(nextSession);
    });

    return () => {
      isMounted = false;
      subscription.unsubscribe();
    };
  }, [loadProfile]);

  const signIn = async ({ email, password }: SignInPayload) => {
    assertSupabaseConfigured();
    const { data, error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      throw error;
    }

    if (data.session) {
      setApiAuthSession(data.session);
      setSession(data.session);
      return await loadProfile(data.session);
    }

    return null;
  };

  const signUp = async ({ name, email, password, emailRedirectTo }: SignUpPayload) => {
    assertSupabaseConfigured();
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          full_name: name,
          name,
        },
        emailRedirectTo,
      },
    });
    if (error) {
      throw error;
    }

    let userProfile = null;
    if (data.session) {
      setApiAuthSession(data.session);
      setSession(data.session);
      userProfile = await loadProfile(data.session);
    }

    return {
      requiresEmailConfirmation: !data.session,
      sessionEstablished: Boolean(data.session),
      user: userProfile,
    };
  };

  const refreshProfile = async () => {
    await loadProfile(session);
  };

  const updateUser = async (updates: Partial<UserProfile>) => {
    const payload = toProfilePatch(updates, user);
    const profile = await apiFetch<BackendProfile>("/profile/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
    if (!session) {
      return;
    }
    const nextUser = buildUserProfile(session, profile, user);
    setUser(nextUser);
    await syncSessionMetadata(session, profile, nextUser);
  };

  const completeOnboarding = async (updates: Partial<UserProfile> = {}) => {
    await updateUser({
      ...updates,
      hasCompletedOnboarding: true,
    });
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        signIn,
        signUp,
        logout,
        updateUser,
        completeOnboarding,
        refreshProfile,
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
