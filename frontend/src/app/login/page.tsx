"use client";

import React, { Suspense, useEffect, useState } from 'react';
import { AnimatePresence, motion as Motion, useReducedMotion } from 'framer-motion';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '../../contexts/AuthContext';
import AuthBackdrop from '../../components/auth/AuthBackdrop';
import AppIcon from '../../components/AppIcon';
import CeltmLogo from '../../components/CeltmLogo';

const initialForm = {
  name: '',
  email: '',
  password: '',
};

const cardTransition = {
  duration: 0.5,
  ease: [0.22, 1, 0.36, 1] as const,
};

const resolveAuthenticatedRoute = (
  hasCompletedOnboarding: boolean,
) => (
  !hasCompletedOnboarding ? '/onboarding' : '/dashboard'
);

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const reduceMotion = useReducedMotion();
  const { user, signIn, signUp } = useAuth();
  
  const [mode, setMode] = useState<'signIn' | 'signUp' | 'adminVerify'>('signIn');
  const [form, setForm] = useState(initialForm);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccessTransition, setIsSuccessTransition] = useState(false);
  const [isNavigating, setIsNavigating] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [infoMessage, setInfoMessage] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [secretCode, setSecretCode] = useState('');

  useEffect(() => {
    if (user && !isSubmitting && !isSuccessTransition && !isNavigating) {
      router.replace(
        resolveAuthenticatedRoute(
          user.hasCompletedOnboarding,
        ),
      );
    }
  }, [isNavigating, isSubmitting, isSuccessTransition, router, user]);

  const toggleMode = () => {
    setMode(prev => prev === 'signIn' ? 'signUp' : 'signIn');
    setForm(initialForm);
    setErrorMessage('');
    setInfoMessage('');
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting || isSuccessTransition) return;

    setIsSubmitting(true);
    setErrorMessage('');

    try {
      let resolvedUser = user;

      if (mode === 'signUp') {
        const result = await signUp({
          name: form.name,
          email: form.email,
          password: form.password,
          emailRedirectTo: `${window.location.origin}/login?confirmed=1`,
        });

        if (result.requiresEmailConfirmation) {
          setIsSubmitting(false);
          setInfoMessage('Please check your email to confirm your account.');
          return;
        }
        if (result.user) {
          resolvedUser = result.user;
        }
      } else if (mode === 'signIn') {
        // First try the admin login
        try {
          const adminRes = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/admin/login`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ username: form.email, password: form.password })
          });

          if (adminRes.ok) {
              const adminData = await adminRes.json();
              localStorage.setItem('adminToken', adminData.access_token);
              setMode('adminVerify');
              setIsSubmitting(false);
              return;
          }
        } catch (adminErr) {
            // Silently fall back to user login if admin API fails or returns non-ok
        }

        // Standard User Login
        const signedInUser = await signIn({ email: form.email, password: form.password });
        if (signedInUser) {
          resolvedUser = signedInUser;
        }
      } else if (mode === 'adminVerify') {
          if (secretCode === 'CELTM2026') {
              localStorage.setItem('adminVerified', 'true');
              setIsSuccessTransition(true);
              await new Promise(r => setTimeout(r, 800));
              setIsNavigating(true);
              setTimeout(() => router.push('/admin'), 800);
              return;
          } else {
              throw new Error('Invalid secure gateway code.');
          }
      }

      setIsSuccessTransition(true);
      await new Promise(r => setTimeout(r, 800));
      setIsNavigating(true);
      
      const nextRoute = resolvedUser ? resolveAuthenticatedRoute(resolvedUser.hasCompletedOnboarding) : '/dashboard';
      setTimeout(() => router.push(nextRoute), 800);
    } catch (err: any) {
      setIsSubmitting(false);
      setErrorMessage(err.message || 'Authentication failed');
    }
  };

  return (
    <AuthBackdrop>
      <div className="relative z-10 flex min-h-screen items-center justify-center px-4 py-12">
        <AnimatePresence mode="wait">
          {isNavigating ? (
            <Motion.div
              key="navigating"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex flex-col items-center justify-center p-12 text-center"
            >
              <div className="mb-6 h-16 w-16 rounded-3xl bg-blue-600/10 p-3 ring-1 ring-blue-600/20">
                <CeltmLogo className="h-full w-full" />
              </div>
              <h2 className="mb-3 text-2xl font-black tracking-tight text-[#0A1128]">
                Bootstrapping CELTM Dashboard...
              </h2>
              <p className="text-sm font-medium leading-relaxed text-slate-500">
                Preparing your personalized learning environment.
              </p>
            </Motion.div>
          ) : (
            <Motion.div
              key="auth-card"
              initial={{ opacity: 0, scale: 0.98, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.98, y: 10 }}
              transition={cardTransition}
              className="w-full max-w-[460px] rounded-[3rem] border border-white/80 bg-white/60 p-10 shadow-[0_32px_90px_rgba(0,0,0,0.05),0_0_0_1px_rgba(255,255,255,0.5)] backdrop-blur-3xl"
            >
              <div className="flex items-center justify-between mb-8">
                <Link href="/" className="group flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-slate-400 transition hover:text-blue-600">
                  <span className="material-symbols-outlined text-sm transition group-hover:-translate-x-1">arrow_back</span>
                  <span>Home</span>
                </Link>
                <CeltmLogo compact className="h-10 w-10 brightness-0" />
              </div>

              <div className="mb-10">
                <h1 className="text-3xl font-black tracking-tight text-[#0A1128]">
                  {mode === 'signIn' ? 'Welcome Back' : 'Join CELTM'}
                </h1>
                <p className="mt-2 text-sm font-medium text-slate-500">
                  {mode === 'signIn' 
                    ? 'Enter your credentials to access your workspace.' 
                    : 'Start your professional learning journey today.'}
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-4 relative">
                <AnimatePresence mode="popLayout" initial={false}>
                  {errorMessage && (
                    <Motion.div
                      layout
                      initial={{ opacity: 0, height: 0, y: -10 }}
                      animate={{ opacity: 1, height: 'auto', y: 0 }}
                      exit={{ opacity: 0, height: 0 }}
                      className="rounded-xl border border-red-200 bg-red-50 p-3 text-[13px] font-medium text-red-600 overflow-hidden"
                    >
                      {errorMessage}
                    </Motion.div>
                  )}
                  
                  {infoMessage && (
                    <Motion.div
                      layout
                      initial={{ opacity: 0, height: 0, y: -10 }}
                      animate={{ opacity: 1, height: 'auto', y: 0 }}
                      exit={{ opacity: 0, height: 0 }}
                      className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-[13px] font-medium text-blue-600 overflow-hidden"
                    >
                      {infoMessage}
                    </Motion.div>
                  )}
                </AnimatePresence>

                {mode === 'adminVerify' ? (
                  <Motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="space-y-6 pt-4"
                  >
                    <div className="mx-auto h-16 w-16 bg-amber-500/10 rounded-3xl flex items-center justify-center">
                       <AppIcon name="lock" className="h-8 w-8 text-amber-500" />
                    </div>
                    <div className="text-center">
                      <h3 className="text-lg font-black text-[#0A1128] uppercase tracking-tight">Restricted Access</h3>
                      <p className="text-xs font-semibold text-slate-500 mt-1">Provide secondary authorization code</p>
                    </div>
                    <input
                      type="password"
                      value={secretCode}
                      onChange={(e) => setSecretCode(e.target.value)}
                      placeholder="••••••••"
                      className="w-full rounded-2xl border-2 border-slate-100 bg-slate-50 px-6 py-4 text-center text-2xl font-black tracking-[0.4em] text-slate-900 outline-none focus:border-amber-500/30 transition-all"
                      autoFocus
                    />
                    <button
                      type="submit"
                      className="w-full h-14 rounded-2xl bg-amber-500 text-black font-black uppercase tracking-[0.2em] text-[11px] shadow-xl shadow-amber-500/20 hover:scale-[1.02] active:scale-100 transition-all"
                    >
                      Verify Identity
                    </button>
                    <button
                      type="button"
                      onClick={() => setMode('signIn')}
                      className="w-full text-[10px] font-black uppercase tracking-widest text-slate-400 hover:text-slate-600"
                    >
                      Cancel
                    </button>
                  </Motion.div>
                ) : (
                  <>
                    <AnimatePresence mode="popLayout" initial={false}>
                      {mode === 'signUp' && (
                        <Motion.div
                          layout
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="space-y-1.5 overflow-hidden"
                        >
                          <label className="block text-[11px] font-black text-slate-700 uppercase tracking-widest pl-1">
                            Display Name
                          </label>
                          <input
                            name="name"
                            value={form.name}
                            onChange={handleChange}
                            className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3.5 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-300 focus:border-google-blue focus:ring-4 focus:ring-google-blue/10 shadow-sm"
                            placeholder="Explorer"
                            required
                          />
                        </Motion.div>
                      )}
                    </AnimatePresence>

                    <Motion.div layout className="space-y-1.5">
                      <label className="block text-[11px] font-black text-slate-700 uppercase tracking-widest pl-1">
                        Email Address
                      </label>
                      <input
                        name="email"
                        type="email"
                        value={form.email}
                        onChange={handleChange}
                        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3.5 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-300 focus:border-google-blue focus:ring-4 focus:ring-google-blue/10 shadow-sm"
                        placeholder="explorer@celtm.ai"
                        required
                      />
                    </Motion.div>

                    <Motion.div layout className="space-y-1.5">
                      <label className="block text-[11px] font-black text-slate-700 uppercase tracking-widest pl-1">
                        Password
                      </label>
                      <div className="relative">
                        <input
                          name="password"
                          type={showPassword ? "text" : "password"}
                          value={form.password}
                          onChange={handleChange}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3.5 pr-12 text-sm text-slate-900 outline-none transition-all placeholder:text-slate-300 focus:border-google-blue focus:ring-4 focus:ring-google-blue/10 shadow-sm"
                          placeholder="••••••••"
                          required
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500 transition-colors"
                        >
                          <AppIcon name={showPassword ? "visibility_off" : "visibility"} className="h-5 w-5" />
                        </button>
                      </div>
                    </Motion.div>

                    <Motion.div layout className="flex items-center justify-between py-1">
                      <label className="flex items-center gap-2 cursor-pointer group">
                        <input type="checkbox" className="h-4 w-4 rounded border-slate-300 text-google-blue focus:ring-google-blue/20 cursor-pointer" />
                        <span className="text-[11px] font-bold text-slate-400 group-hover:text-slate-600 transition-colors uppercase tracking-wider">Remember me</span>
                      </label>
                      <button type="button" className="text-[11px] font-bold text-google-blue hover:underline uppercase tracking-wider">
                        Forgot Password?
                      </button>
                    </Motion.div>

                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="relative mt-8 flex h-14 w-full items-center justify-center rounded-2xl bg-[#0A1128] text-[11px] font-black uppercase tracking-[0.3em] text-white shadow-[0_20px_40px_rgba(10,17,40,0.2)] transition-all hover:translate-y-[-2px] hover:shadow-[0_25px_50px_rgba(10,17,40,0.3)] active:translate-y-[0px] disabled:translate-y-0 disabled:opacity-70"
                    >
                      {isSubmitting ? (
                        <div className="h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                      ) : (
                        <span>{mode === 'signIn' ? 'ENTER WORKSPACE' : 'INITIALIZE PROFILE'}</span>
                      )}
                    </button>
                  </>
                )}

                <Motion.div layout className="relative py-6 flex items-center justify-center">
                  <div className="absolute inset-x-0 border-t border-slate-100" />
                  <span className="relative bg-[#fafafa]/80 px-4 text-[10px] font-bold text-slate-300 uppercase tracking-[0.2em] backdrop-blur-sm">CELTM Secure</span>
                </Motion.div>

                <Motion.button
                  layout
                  type="button"
                  className="w-full flex items-center justify-center gap-4 rounded-2xl border border-slate-200 bg-white px-4 py-5 text-[12px] font-black text-slate-700 transition-all hover:bg-slate-50 hover:border-slate-300 active:scale-[0.98] tracking-[0.18em] shadow-sm"
                >
                  <svg height="18" viewBox="0 0 24 24" width="18">
                    <g transform="matrix(1, 0, 0, 1, 27.009001, -39.238998)">
                      <path d="M -3.264 51.509 C -3.264 50.719 -3.334 49.969 -3.454 49.239 L -14.754 49.239 L -14.754 53.749 L -8.284 53.749 C -8.574 55.229 -9.424 56.479 -10.684 57.329 L -10.684 60.329 L -6.824 60.329 C -4.564 58.239 -3.264 55.159 -3.264 51.509 Z" fill="#4285F4" />
                      <path d="M -14.754 63.239 C -11.514 63.239 -8.804 62.159 -6.824 60.329 L -10.684 57.329 C -11.764 58.049 -13.134 58.489 -14.754 58.489 C -17.884 58.489 -20.534 56.379 -21.484 53.529 L -25.464 53.529 L -25.464 56.619 C -23.494 60.539 -19.444 63.239 -14.754 63.239 Z" fill="#34A853" />
                      <path d="M -21.484 53.529 C -21.734 52.809 -21.864 52.039 -21.864 51.239 C -21.864 50.439 -21.724 49.669 -21.484 48.949 L -21.484 45.859 L -25.464 45.859 C -26.284 47.479 -26.754 49.299 -26.754 51.239 C -26.754 53.179 -26.284 54.999 -25.464 56.619 L -21.484 53.529 Z" fill="#FBBC05" />
                      <path d="M -14.754 43.989 C -12.984 43.989 -11.404 44.599 -10.154 45.789 L -6.734 42.369 C -8.804 40.429 -11.514 39.239 -14.754 39.239 C -19.444 39.239 -23.494 41.939 -25.464 45.859 L -21.484 48.949 C -20.534 46.099 -17.884 43.989 -14.754 43.989 Z" fill="#EA4335" />
                    </g>
                  </svg>
                  ACCESS WITH GOOGLE HUB
                </Motion.button>

                <Motion.div layout className="pt-6 text-center">
                  <p className="text-xs font-bold text-slate-400 tracking-wide">
                    {mode === 'signIn' ? "NEW TO CELTM?" : "ALREADY ENROLLED?"}{' '}
                    <button
                      type="button"
                      onClick={toggleMode}
                      className="text-google-blue hover:underline uppercase"
                    >
                      {mode === 'signIn' ? 'CREATE ACCOUNT' : 'SECURE SIGN IN'}
                    </button>
                  </p>
                </Motion.div>
              </form>
            </Motion.div>
          )}
        </AnimatePresence>
      </div>
    </AuthBackdrop>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="min-screen bg-[#fafafa]" />}>
      <LoginPageContent />
    </Suspense>
  );
}
