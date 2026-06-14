"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion as Motion, AnimatePresence } from "framer-motion";
import AuthBackdrop from "@/components/auth/AuthBackdrop";
import AppIcon from "@/components/AppIcon";
import CeltmLogo from "@/components/CeltmLogo";
import { useAuth } from "@/contexts/AuthContext";
import { supabase } from "@/lib/supabase";

function ResetPasswordPage() {
  const router = useRouter();
  const { updatePassword, logout } = useAuth();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isCheckingSession, setIsCheckingSession] = useState(true);
  const [hasRecoverySession, setHasRecoverySession] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    const checkSession = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();

      if (!isMounted) {
        return;
      }

      setHasRecoverySession(Boolean(session));
      setIsCheckingSession(false);
    };

    void checkSession();
    const retryTimer = window.setTimeout(() => {
      void checkSession();
    }, 600);

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      if (!isMounted) {
        return;
      }

      if (event === "PASSWORD_RECOVERY" || session) {
        setHasRecoverySession(Boolean(session));
        setIsCheckingSession(false);
      }
    });

    return () => {
      isMounted = false;
      window.clearTimeout(retryTimer);
      subscription.unsubscribe();
    };
  }, []);

  const submitNewPassword = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setMessage("");

    if (password.length < 8) {
      setError("Use at least 8 characters for your new password.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setIsSubmitting(true);
    try {
      await updatePassword(password);
      setMessage("Password updated. Use your new password to log in.");
      setPassword("");
      setConfirmPassword("");
      await logout();
      window.setTimeout(() => {
        router.replace("/login?reset=1");
      }, 1200);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Password could not be updated.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthBackdrop>
      <div className="relative z-10 flex min-h-screen items-center justify-center px-4 py-10">
        <Motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex min-h-[560px] w-full max-w-[440px] flex-col justify-center rounded-[2.5rem] border border-white/80 bg-white/70 p-10 shadow-[0_32px_90px_rgba(0,0,0,0.08)] backdrop-blur-3xl"
        >
          <div className="mb-7 flex items-center justify-between">
            <Link href="/login" className="text-sm font-black uppercase tracking-[0.18em] text-slate-400 transition-colors hover:text-blue-600">
              Login
            </Link>
            <CeltmLogo compact className="h-10 w-10 brightness-0" />
          </div>

          <div className="mb-8">
            <p className="text-xs font-black uppercase tracking-[0.24em] text-blue-600">Account recovery</p>
            <h1 className="mt-3 text-4xl font-black tracking-tight text-[#0A1128]">Reset password</h1>
            <p className="mt-3 text-base font-medium leading-7 text-slate-500">
              Set a new password from the secure link sent to your email.
            </p>
          </div>

          <AnimatePresence mode="wait">
            {isCheckingSession ? (
              <Motion.div
                key="checking"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex h-40 items-center justify-center"
              >
                <span className="h-7 w-7 animate-spin rounded-full border-2 border-blue-100 border-t-blue-600" />
              </Motion.div>
            ) : hasRecoverySession ? (
              <Motion.form
                key="form"
                onSubmit={submitNewPassword}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                transition={{ duration: 0.2 }}
                className="space-y-4"
              >
                {error ? <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-600">{error}</div> : null}
                {message ? <div className="rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-700">{message}</div> : null}

                <Field label="New password">
                  <PasswordField value={password} onChange={setPassword} placeholder="New password" />
                </Field>
                <Field label="Confirm password">
                  <PasswordField value={confirmPassword} onChange={setConfirmPassword} placeholder="Confirm password" />
                </Field>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="mt-3 flex h-14 w-full items-center justify-center rounded-2xl bg-[#0A1128] text-[11px] font-black uppercase tracking-[0.25em] text-white shadow-[0_20px_40px_rgba(10,17,40,0.2)] transition hover:-translate-y-0.5 disabled:opacity-60"
                >
                  {isSubmitting ? <span className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-white" /> : "Update Password"}
                </button>
              </Motion.form>
            ) : (
              <Motion.div
                key="expired"
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                transition={{ duration: 0.2 }}
                className="rounded-[2rem] border border-amber-200 bg-amber-50 p-6 text-center"
              >
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-amber-600 shadow-sm">
                  <AppIcon name="warning" className="h-7 w-7" />
                </div>
                <h2 className="mt-5 text-xl font-black tracking-tight text-[#0A1128]">Reset link expired</h2>
                <p className="mt-3 text-sm font-semibold leading-6 text-amber-800">
                  Request a fresh password reset link from the login page and open it from the same browser.
                </p>
                <Link
                  href="/login"
                  className="mt-6 flex h-12 w-full items-center justify-center rounded-2xl bg-[#0A1128] text-[11px] font-black uppercase tracking-[0.22em] text-white transition hover:-translate-y-0.5"
                >
                  Back to login
                </Link>
              </Motion.div>
            )}
          </AnimatePresence>
        </Motion.div>
      </div>
      <style jsx global>{`
        .input {
          width: 100%;
          border-radius: 1.25rem;
          border: 1px solid rgb(226 232 240);
          background: white;
          padding: 1rem 1.25rem;
          font-size: 0.95rem;
          color: rgb(15 23 42);
          outline: none;
          transition: all 0.2s cubic-bezier(0.22, 1, 0.36, 1);
        }
        .input:focus {
          border-color: rgb(37 99 235 / 0.55);
          box-shadow: 0 0 0 4px rgb(37 99 235 / 0.1);
        }
      `}</style>
    </AuthBackdrop>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-2">
      <span className="pl-1 text-xs font-black uppercase tracking-widest text-slate-700">{label}</span>
      {children}
    </label>
  );
}

function PasswordField({ value, onChange, placeholder }: { value: string; onChange: (value: string) => void; placeholder?: string }) {
  const [show, setShow] = useState(false);

  return (
    <div className="relative">
      <input
        required
        type={show ? "text" : "password"}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="input"
        placeholder={placeholder}
        style={{ paddingRight: "3.5rem" }}
      />
      <button
        type="button"
        onClick={() => setShow(!show)}
        className="absolute right-4 top-1/2 -translate-y-1/2 text-[10px] font-bold uppercase tracking-widest text-slate-400 transition-colors hover:text-slate-600 focus:outline-none"
      >
        {show ? "Hide" : "Show"}
      </button>
    </div>
  );
}

export default ResetPasswordPage;
