"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { motion as Motion, AnimatePresence } from "framer-motion";
import { apiBaseUrl } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import AuthBackdrop from "@/components/auth/AuthBackdrop";
import AppIcon from "@/components/AppIcon";
import CeltmLogo from "@/components/CeltmLogo";
import ThemedSelect from "@/components/ThemedSelect";

interface Department {
  id: string;
  name: string;
}

interface Institution {
  id: string;
  name: string;
  domain: string;
  departments: Department[];
}

const initialStudentForm = {
  name: "",
  email: "",
  password: "",
  institutionId: "",
  departmentId: "",
};

const initialLoginForm = {
  email: "",
  password: "",
  mfaCode: "",
};

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, signIn, signUp, requestPasswordReset } = useAuth();
  const [accountType, setAccountType] = useState<"student" | "institution">("student");
  const [studentMode, setStudentMode] = useState<"signIn" | "signUp">("signIn");
  const [studentForm, setStudentForm] = useState(initialStudentForm);
  const [institutionForm, setInstitutionForm] = useState(initialLoginForm);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [confirmationPopupOpen, setConfirmationPopupOpen] = useState(false);
  const [resetPopupOpen, setResetPopupOpen] = useState(false);
  const [resetEmail, setResetEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (user) {
      router.replace("/dashboard");
    }
  }, [router, user]);

  useEffect(() => {
    if (searchParams.get("reset") === "1") {
      setMessage("Password updated. Log in with your new password.");
    }
  }, [searchParams]);

  useEffect(() => {
    let active = true;
    fetch(`${apiBaseUrl}/institutions`)
      .then((res) => (res.ok ? res.json() : []))
      .then((payload) => {
        if (active) setInstitutions(payload);
      })
      .catch(() => {
        if (active) setInstitutions([]);
      });
    return () => {
      active = false;
    };
  }, []);

  const selectedInstitution = useMemo(
    () => institutions.find((item) => item.id === studentForm.institutionId) ?? null,
    [institutions, studentForm.institutionId],
  );

  const selectedDepartment = useMemo(
    () => selectedInstitution?.departments.find((item) => item.id === studentForm.departmentId) ?? null,
    [selectedInstitution, studentForm.departmentId],
  );

  const submitStudent = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setMessage("");
    setIsSubmitting(true);
    try {
      if (studentMode === "signIn") {
        await signIn({ email: studentForm.email, password: studentForm.password });
        router.push("/dashboard");
        return;
      }

      if (!selectedInstitution || !selectedDepartment) {
        throw new Error("Select your institute and department.");
      }
      if (selectedInstitution.domain && !studentForm.email.toLowerCase().endsWith(`@${selectedInstitution.domain.toLowerCase()}`)) {
        throw new Error(`Use your ${selectedInstitution.name} college email ending with @${selectedInstitution.domain}.`);
      }

      const result = await signUp({
        name: studentForm.name,
        email: studentForm.email,
        password: studentForm.password,
        institutionId: selectedInstitution.id,
        departmentId: selectedDepartment.id,
        institutionName: selectedInstitution.name,
        departmentName: selectedDepartment.name,
        emailRedirectTo: `${window.location.origin}/login?confirmed=1`,
      });

      if (result.requiresEmailConfirmation) {
        setStudentMode("signIn");
        setStudentForm((current) => ({
          ...initialStudentForm,
          email: current.email,
        }));
        setMessage("Confirmation sent to begin login.");
        setConfirmationPopupOpen(true);
        return;
      }
      router.push("/dashboard");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Student authentication failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitPasswordReset = async (event: React.FormEvent) => {
    event.preventDefault();
    const normalizedEmail = resetEmail.trim().toLowerCase();
    setError("");
    setMessage("");

    if (!normalizedEmail) {
      setError("Enter your email address to receive a reset link.");
      return;
    }

    setIsSubmitting(true);
    try {
      await requestPasswordReset(normalizedEmail, `${window.location.origin}/reset-password`);
      setResetPopupOpen(false);
      setMessage("Password reset link sent. Check your email.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Password reset email could not be sent.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const submitInstitution = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setMessage("");
    setIsSubmitting(true);
    try {
      const response = await fetch(`${apiBaseUrl}/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: institutionForm.email,
          password: institutionForm.password,
          mfa_code: institutionForm.mfaCode || undefined,
        }),
      });
      const payload = await response.json() as { detail?: string; access_token?: string; role?: string };
      if (!response.ok) {
        throw new Error(payload.detail || "Invalid institution admin credentials.");
      }
      window.localStorage.removeItem("adminToken");
      window.localStorage.removeItem("adminRole");
      window.sessionStorage.setItem("adminToken", payload.access_token || "");
      window.sessionStorage.setItem("adminRole", payload.role || "");
      router.push("/admin");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Institution login failed.");
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
          className="w-full max-w-[440px] rounded-[2.5rem] border border-white/80 bg-white/70 p-10 shadow-[0_32px_90px_rgba(0,0,0,0.08)] backdrop-blur-3xl min-h-[600px] flex flex-col justify-center"
        >
          <div className="mb-7 flex items-center justify-between">
            <Link href="/" className="text-sm font-black uppercase tracking-[0.18em] text-slate-400 hover:text-blue-600 transition-colors">
              Home
            </Link>
            <CeltmLogo compact className="h-10 w-10 brightness-0" />
          </div>

          <div className="mb-8">
            <p className="text-xs font-black uppercase tracking-[0.24em] text-blue-600">CELTM Phase 1</p>
            <h1 className="mt-3 text-4xl font-black tracking-tight text-[#0A1128]">Login</h1>
            <p className="mt-3 text-base font-medium leading-7 text-slate-500">
              Students enter the resume-first dashboard. Institution heads use admin access created by CELTM super admin.
            </p>
          </div>

          <div className="mb-6 grid grid-cols-2 gap-2 rounded-2xl bg-slate-100 p-1">
            {[
              { key: "student", label: "Student" },
              { key: "institution", label: "Institution" },
            ].map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => {
                  setAccountType(item.key as "student" | "institution");
                  setError("");
                  setMessage("");
                  setConfirmationPopupOpen(false);
                  setResetPopupOpen(false);
                }}
                className={`rounded-xl px-4 py-3 text-[11px] font-black uppercase tracking-[0.16em] transition ${
                  accountType === item.key ? "bg-white text-blue-700 shadow-sm" : "text-slate-500"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>

          {error ? <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-600">{error}</div> : null}
          {message ? <div className="mb-4 rounded-2xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm font-semibold text-blue-700">{message}</div> : null}

          <div className="relative">
            <AnimatePresence mode="wait">
              {accountType === "student" ? (
                <Motion.div
                  key="student-form"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 10 }}
                  transition={{ duration: 0.2 }}
                >
                  <form onSubmit={submitStudent} className="space-y-4">
                    <div className="flex justify-end">
                      <button
                        type="button"
                        onClick={() => {
                          setStudentMode((mode) => (mode === "signIn" ? "signUp" : "signIn"));
                          setError("");
                          setMessage("");
                          setConfirmationPopupOpen(false);
                          setResetPopupOpen(false);
                        }}
                        className="text-[11px] font-black uppercase tracking-widest text-blue-600"
                      >
                        {studentMode === "signIn" ? "New student signup" : "Existing student signin"}
                      </button>
                    </div>

                    <AnimatePresence mode="wait">
                      {studentMode === "signUp" ? (
                        <Motion.div
                          key="signup-fields"
                          initial={{ opacity: 0, height: 0, marginTop: 0 }}
                          animate={{ opacity: 1, height: "auto", marginTop: 16 }}
                          exit={{ opacity: 0, height: 0, marginTop: 0 }}
                          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                          className="space-y-4 overflow-hidden"
                        >
                          <Field label="Full name">
                            <input required value={studentForm.name} onChange={(e) => setStudentForm({ ...studentForm, name: e.target.value })} className="input" placeholder="Your name" />
                          </Field>
                          <div className="grid gap-4 sm:grid-cols-2">
                            <Field label="Institute">
                              <ThemedSelect
                                required
                                value={studentForm.institutionId}
                                onChange={(value) => setStudentForm({ ...studentForm, institutionId: value, departmentId: "" })}
                                placeholder="Select institute"
                                options={institutions.map((item) => ({ value: item.id, label: item.name }))}
                                buttonClassName="min-h-12 rounded-xl border-slate-200 bg-white/90 text-[#0A1128]"
                              />
                            </Field>
                            <Field label="Department">
                              <ThemedSelect
                                required
                                value={studentForm.departmentId}
                                onChange={(value) => setStudentForm({ ...studentForm, departmentId: value })}
                                placeholder="Select department"
                                disabled={!selectedInstitution}
                                options={(selectedInstitution?.departments ?? []).map((item) => ({ value: item.id, label: item.name }))}
                                buttonClassName="min-h-12 rounded-xl border-slate-200 bg-white/90 text-[#0A1128]"
                              />
                            </Field>
                          </div>
                        </Motion.div>
                      ) : null}
                    </AnimatePresence>

                    <Field label={studentMode === "signUp" ? "College email" : "Email"}>
                      <input required type="email" value={studentForm.email} onChange={(e) => setStudentForm({ ...studentForm, email: e.target.value })} className="input" placeholder="name@college.edu" />
                    </Field>
                    <Field label="Password">
                      <PasswordField value={studentForm.password} onChange={(v) => setStudentForm({ ...studentForm, password: v })} placeholder="Password" />
                    </Field>
                    {studentMode === "signIn" ? (
                      <div className="-mt-2 flex justify-end">
                        <button
                          type="button"
                          onClick={() => {
                            setResetEmail(studentForm.email);
                            setResetPopupOpen(true);
                            setError("");
                            setMessage("");
                          }}
                          className="text-[10px] font-black uppercase tracking-widest text-blue-600 transition hover:text-blue-800"
                        >
                          Forgot password?
                        </button>
                      </div>
                    ) : null}
                    <SubmitButton loading={isSubmitting} label={studentMode === "signIn" ? "Enter Dashboard" : "Create Student Account"} />
                  </form>
                </Motion.div>
              ) : (
                <Motion.div
                  key="institution-form"
                  initial={{ opacity: 0, x: 10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  transition={{ duration: 0.2 }}
                >
                  <form onSubmit={submitInstitution} className="space-y-4">
                    <Field label="Institution head / super-admin email">
                      <input required type="email" value={institutionForm.email} onChange={(e) => setInstitutionForm({ ...institutionForm, email: e.target.value })} className="input" placeholder="hod@institute.edu" />
                    </Field>
                    <Field label="Password">
                      <PasswordField value={institutionForm.password} onChange={(v) => setInstitutionForm({ ...institutionForm, password: v })} placeholder="Admin password" />
                    </Field>
                    <Field label="MFA code">
                      <input
                        inputMode="numeric"
                        pattern="[0-9]*"
                        maxLength={6}
                        value={institutionForm.mfaCode}
                        onChange={(e) => setInstitutionForm({ ...institutionForm, mfaCode: e.target.value.replace(/\D/g, "").slice(0, 6) })}
                        className="input"
                        placeholder="6-digit code if enabled"
                      />
                    </Field>
                    <SubmitButton loading={isSubmitting} label="Enter Admin Console" />
                    <p className="text-xs leading-5 text-slate-500">
                      Student credentials are not valid here. Institution access is created only by CELTM super admin.
                    </p>
                  </form>
                </Motion.div>
              )}
            </AnimatePresence>
          </div>
        </Motion.div>
      </div>
      <AnimatePresence>
        {confirmationPopupOpen ? (
          <Motion.div
            className="fixed inset-0 z-[10000] flex items-center justify-center bg-slate-950/35 px-4 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            role="presentation"
          >
            <Motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="signup-confirmation-title"
              initial={{ opacity: 0, y: 16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.98 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              className="w-full max-w-sm rounded-[2rem] border border-white/80 bg-white p-7 text-center shadow-[0_32px_90px_rgba(10,17,40,0.22)]"
            >
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                <AppIcon name="mail" className="h-7 w-7" />
              </div>
              <h2 id="signup-confirmation-title" className="mt-5 text-2xl font-black tracking-tight text-[#0A1128]">
                Confirmation sent
              </h2>
              <p className="mt-3 text-sm font-semibold leading-6 text-slate-500">
                Confirmation sent to begin login.
              </p>
              <button
                type="button"
                onClick={() => setConfirmationPopupOpen(false)}
                className="mt-6 flex h-12 w-full items-center justify-center rounded-2xl bg-[#0A1128] text-[11px] font-black uppercase tracking-[0.22em] text-white transition hover:-translate-y-0.5"
              >
                Begin login
              </button>
            </Motion.div>
          </Motion.div>
        ) : null}
      </AnimatePresence>
      <AnimatePresence>
        {resetPopupOpen ? (
          <Motion.div
            className="fixed inset-0 z-[10000] flex items-center justify-center bg-slate-950/35 px-4 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            role="presentation"
          >
            <Motion.form
              onSubmit={submitPasswordReset}
              role="dialog"
              aria-modal="true"
              aria-labelledby="reset-password-title"
              initial={{ opacity: 0, y: 16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.98 }}
              transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
              className="w-full max-w-sm rounded-[2rem] border border-white/80 bg-white p-7 shadow-[0_32px_90px_rgba(10,17,40,0.22)]"
            >
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
                <AppIcon name="mail" className="h-7 w-7" />
              </div>
              <h2 id="reset-password-title" className="mt-5 text-center text-2xl font-black tracking-tight text-[#0A1128]">
                Reset password
              </h2>
              <p className="mt-3 text-center text-sm font-semibold leading-6 text-slate-500">
                Enter your student email and CELTM will send a secure password reset link.
              </p>
              <div className="mt-6">
                <Field label="Email">
                  <input
                    required
                    type="email"
                    value={resetEmail}
                    onChange={(event) => setResetEmail(event.target.value)}
                    className="input"
                    placeholder="name@college.edu"
                  />
                </Field>
              </div>
              <div className="mt-6 grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setResetPopupOpen(false)}
                  className="flex h-12 items-center justify-center rounded-2xl border border-slate-200 bg-white text-[10px] font-black uppercase tracking-[0.18em] text-slate-500 transition hover:bg-slate-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex h-12 items-center justify-center rounded-2xl bg-[#0A1128] text-[10px] font-black uppercase tracking-[0.18em] text-white transition hover:-translate-y-0.5 disabled:opacity-60"
                >
                  {isSubmitting ? <span className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-white" /> : "Send link"}
                </button>
              </div>
            </Motion.form>
          </Motion.div>
        ) : null}
      </AnimatePresence>
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
        select.input {
          appearance: none;
          background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
          background-repeat: no-repeat;
          background-position: right 1rem center;
          background-size: 1em;
          padding-right: 2.5rem;
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

function PasswordField({ value, onChange, placeholder }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        required
        type={show ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input"
        placeholder={placeholder}
        style={{ paddingRight: "3.5rem" }}
      />
      <button
        type="button"
        onClick={() => setShow(!show)}
        className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 font-bold text-[10px] uppercase tracking-widest transition-colors focus:outline-none"
      >
        {show ? "Hide" : "Show"}
      </button>
    </div>
  );
}

function SubmitButton({ loading, label }: { loading: boolean; label: string }) {
  return (
    <button
      type="submit"
      disabled={loading}
      className="mt-3 flex h-14 w-full items-center justify-center rounded-2xl bg-[#0A1128] text-[11px] font-black uppercase tracking-[0.25em] text-white shadow-[0_20px_40px_rgba(10,17,40,0.2)] transition hover:-translate-y-0.5 disabled:opacity-60"
    >
      {loading ? <span className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-white" /> : label}
    </button>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-white" />}>
      <LoginPageContent />
    </Suspense>
  );
}
