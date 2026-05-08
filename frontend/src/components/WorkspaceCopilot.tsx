"use client";

import React, { useEffect, useMemo, useState, useRef } from 'react';
import { AnimatePresence, motion as Motion, useReducedMotion } from 'framer-motion';
import { usePathname } from 'next/navigation';
import AppIcon from './AppIcon';
import { assistantKnowledge } from '../constants/assistantKnowledge';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';
import { apiFetch } from '../lib/api';

const storageKey = 'celtm_workspace_copilot';

interface AssistantSource {
  title: string;
  detail: string;
  tag: string;
}

interface AssistantContextData {
  title: string;
  intro: string;
  nextAction?: string;
  prompts: string[];
  sources: AssistantSource[];
}

interface CopilotResponse {
  answer: string;
  confidence: number;
  sources: AssistantSource[];
}

interface UserMessage {
  id: string;
  role: 'user';
  content: string;
  pathname: string;
}

interface AssistantMessage {
  id: string;
  role: 'assistant';
  content: string;
  confidence: number;
  sources: AssistantSource[];
  pathname: string;
}

type CopilotMessage = UserMessage | AssistantMessage;

interface AssistantState {
  isOpen: boolean;
  view: 'compact' | 'sidebar' | 'full';
  messages: CopilotMessage[];
}

const defaultState: AssistantState = {
  isOpen: false,
  view: 'compact',
  messages: [],
};

const sharedSpring = { duration: 0.34, ease: [0.22, 1, 0.36, 1] as const };

const SourceCard = ({ source, isDark }: { source: AssistantSource; isDark: boolean }) => (
  <div className={`rounded-[1.4rem] border p-4 backdrop-blur-xl transition-colors ${
    isDark ? 'border-white/[0.04] bg-white/[0.08]' : 'border-slate-200 dark:border-transparent bg-slate-100/60'
  }`}>
    <div className="flex items-center justify-between gap-3">
      <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${
        isDark ? 'text-white/58' : 'text-slate-500'
      }`}>
        {source.tag}
      </p>
      <AppIcon name="hub" className={`h-4 w-4 ${isDark ? 'text-white/40' : 'text-slate-400'}`} />
    </div>
    <p className={`mt-3 text-sm font-semibold ${isDark ? 'text-white' : 'text-slate-900'}`}>{source.title}</p>
    <p className={`mt-2 text-sm leading-6 ${isDark ? 'text-white/68' : 'text-slate-600'}`}>{source.detail}</p>
  </div>
);

const MessageBubble = ({ message, isDark }: { message: CopilotMessage; isDark: boolean }) => (
  <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
    <div
      className={`max-w-[88%] rounded-[1.45rem] px-4 py-3 text-[15px] leading-7 shadow-sm ${
        message.role === 'user'
          ? 'rounded-br-md bg-gradient-to-br from-[#7b72f2] via-[#a48cff] to-[#efbccf] text-white shadow-[0_16px_30px_rgba(123,114,242,0.26)]'
          : `rounded-bl-md border backdrop-blur-xl ${
              isDark 
                ? 'border-white/[0.04] bg-white/[0.09] text-white/84' 
                : 'border-slate-200 dark:border-transparent bg-white shadow-sm text-slate-800'
            }`
      }`}
    >
      {message.role === 'assistant' && (
        <div className={`mb-2 flex items-center justify-between gap-3 text-[10px] font-semibold uppercase tracking-[0.2em] ${
          isDark ? 'text-white/42' : 'text-slate-400'
        }`}>
          <span>RAG CHAT BOT</span>
          <span>{Math.round((message.confidence ?? 0.87) * 100)}%</span>
        </div>
      )}
      <div className="whitespace-pre-wrap">{message.content}</div>
    </div>
  </div>
);

const ControlButton = ({ active, icon, label, onClick, isDark }: { active: boolean, icon: string, label: string, onClick: () => void, isDark: boolean }) => (
  <button
    type="button"
    onClick={onClick}
    title={label}
    aria-label={label}
    className={`inline-flex h-10 w-10 items-center justify-center rounded-full transition ${
      active
        ? (isDark ? 'bg-white/18 text-white' : 'bg-slate-200 text-slate-900')
        : (isDark ? 'bg-white/[0.08] text-white/62 hover:bg-white/[0.14] hover:text-white' : 'bg-slate-100 text-slate-400 hover:bg-slate-200 hover:text-slate-700')
    }`}
  >
    <AppIcon name={icon} className="h-4 w-4" />
  </button>
);

const AssistantShell = ({ children, isDark, className = '' }: { children: React.ReactNode, isDark: boolean, className?: string }) => (
  <div
    className={`relative overflow-hidden border transition-colors shadow-[0_30px_70px_rgba(0,0,0,0.3)] backdrop-blur-md ${
      isDark 
        ? 'border-white/[0.04] bg-[rgba(10,10,12,0.82)]' 
        : 'border-slate-200 dark:border-transparent bg-white/94 shadow-[0_30px_70px_rgba(0,0,0,0.1)]'
    } ${className}`}
  >
    {isDark && (
      <>
        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(255,255,255,0.12),rgba(255,255,255,0.02)_26%,rgba(255,255,255,0.01)_100%),radial-gradient(circle_at_top_left,rgba(255,255,255,0.12),transparent_28%),radial-gradient(circle_at_top_right,rgba(168,139,250,0.14),transparent_24%),radial-gradient(circle_at_bottom_left,rgba(244,189,208,0.14),transparent_26%),radial-gradient(circle_at_bottom_right,rgba(255,255,255,0.08),transparent_24%)]" />
        <div className="pointer-events-none absolute inset-x-10 top-0 h-24 rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.12),transparent_68%)] blur-3xl" />
        <div className="pointer-events-none absolute inset-x-16 bottom-0 h-32 rounded-full bg-[radial-gradient(circle,rgba(244,189,208,0.16),transparent_62%)] blur-3xl" />
      </>
    )}
    {!isDark && (
      <>
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(66,133,244,0.04),transparent_28%),radial-gradient(circle_at_top_right,rgba(234,67,53,0.04),transparent_24%)]" />
        <div className="pointer-events-none absolute inset-x-10 top-0 h-24 rounded-full bg-[radial-gradient(circle,rgba(66,133,244,0.05),transparent_68%)] blur-3xl" />
      </>
    )}
    <div className="relative h-full">{children}</div>
  </div>
);

const WorkspaceCopilot = () => {
  const pathname = usePathname();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const reduceMotion = useReducedMotion();
  const { user } = useAuth();
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [assistantState, setAssistantState] = useState<AssistantState>(defaultState);
  const [isLauncherHovered, setIsLauncherHovered] = useState(false);
  const [hasHydratedAssistantState, setHasHydratedAssistantState] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const locationPathname = pathname || '/';
  const isAssessment = locationPathname.includes('/assessments/quiz') || locationPathname.includes('/assessments/written-protocol');

  const context = useMemo(
    () =>
      (assistantKnowledge as Record<string, AssistantContextData>)[locationPathname] ??
      (assistantKnowledge as Record<string, AssistantContextData>).default,
    [locationPathname],
  );

  const currentMessages = useMemo(
    () => assistantState.messages.filter((message) => message.pathname === locationPathname),
    [assistantState.messages, locationPathname],
  );

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    try {
      const rawState = localStorage.getItem(storageKey);
      if (!rawState) {
        return;
      }

      const parsedState = JSON.parse(rawState) as Partial<AssistantState>;
      const nextState: AssistantState = {
        isOpen: typeof parsedState.isOpen === 'boolean' ? parsedState.isOpen : false,
        view:
          parsedState.view === 'compact' || parsedState.view === 'sidebar' || parsedState.view === 'full'
            ? parsedState.view
            : 'compact',
        messages: Array.isArray(parsedState.messages) ? parsedState.messages : [],
      };
      setAssistantState(nextState);
    } catch {
      // Ignore invalid persisted state and keep defaults.
    } finally {
      setHasHydratedAssistantState(true);
    }
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined' && hasHydratedAssistantState) {
      localStorage.setItem(storageKey, JSON.stringify(assistantState));
    }
  }, [assistantState, hasHydratedAssistantState]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [currentMessages, loading]);

  const setView = (view: AssistantState['view']) => {
    setAssistantState((current) => ({ ...current, isOpen: true, view }));
  };

  const closeAssistant = () => {
    setAssistantState((current) => ({ ...current, isOpen: false }));
  };

  const appendAssistantMessage = async (question: string) => {
    setLoading(true);
    // Removed artificial delay for low-latency response

    let response: CopilotResponse;
    try {
      response = await apiFetch<CopilotResponse>('/copilot/chat', {
        method: 'POST',
        body: JSON.stringify({
          message: question,
          page_context: locationPathname,
          role_context: user?.role || "Student",
        }),
      });
    } catch {
      response = {
        answer: `I couldn't retrieve live workspace context for this question yet. Try again in a moment or rephrase the prompt for ${user?.name || 'your'} current page.`,
        confidence: 0.42,
        sources: context.sources,
      };
    }

    setAssistantState((current) => ({
      ...current,
      messages: [
        ...current.messages,
        {
          id: `${Date.now()}-assistant`,
          role: 'assistant',
          content: response.answer,
          confidence: response.confidence,
        sources: response.sources,
        pathname: locationPathname,
        } satisfies AssistantMessage,
      ].slice(-18),
    }));
    setLoading(false);
  };

  const submitQuestion = async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || loading) {
      return;
    }

    setAssistantState((current) => ({
      ...current,
      isOpen: true,
      messages: [
        ...current.messages,
        {
          id: `${Date.now()}-user`,
          role: 'user',
          content: trimmed,
          pathname: locationPathname,
        } satisfies UserMessage,
      ].slice(-18),
    }));
    setDraft('');
    await appendAssistantMessage(trimmed);
  };

  const latestAssistantMessage = [...currentMessages]
    .reverse()
    .find((message) => message.role === 'assistant');

  const sourceCards = latestAssistantMessage?.sources ?? context.sources;

  const sharedHeader = (
    <div className={`flex items-start justify-between gap-4 border-b px-5 py-4 transition-colors ${
      isDark ? 'border-white/[0.03]' : 'border-slate-200 dark:border-transparent bg-slate-50/50'
    }`}>
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-google-blue via-google-red to-google-yellow text-white shadow-[0_16px_32px_rgba(66,133,244,0.3)]">
          <AppIcon name="forum" className="h-5 w-5" />
        </div>
        <div>
          <p className={`text-[10px] font-bold uppercase tracking-[0.24em] ${
            isDark ? 'text-white/46' : 'text-slate-500'
          }`}>
            RAG CHAT BOT
          </p>
          <h3 className={`mt-0.5 text-lg font-black tracking-tight ${
            isDark ? 'text-white' : 'text-slate-900'
          }`}>{context.title}</h3>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <ControlButton
          active={assistantState.view === 'compact'}
          icon="forum"
          label="Box"
          onClick={() => setView('compact')}
          isDark={isDark}
        />
        <ControlButton
          active={assistantState.view === 'sidebar'}
          icon="chevron_left"
          label="Sidebar"
          onClick={() => setView('sidebar')}
          isDark={isDark}
        />
        <ControlButton
          active={assistantState.view === 'full'}
          icon="open_in_new"
          label="Full"
          onClick={() => setView('full')}
          isDark={isDark}
        />
        <button
          type="button"
          onClick={closeAssistant}
          className={`inline-flex h-10 w-10 items-center justify-center rounded-full transition ${
            isDark 
              ? 'bg-white/[0.08] text-white/62 hover:bg-white/[0.14] hover:text-white' 
              : 'bg-slate-100 text-slate-400 hover:bg-slate-200 hover:text-slate-700'
          }`}
          aria-label="Close assistant"
        >
          <AppIcon name="close" className="h-4 w-4" />
        </button>
      </div>
    </div>
  );

  const suggestionPanel = (
    <div className={`rounded-[1.55rem] border p-4 backdrop-blur-xl transition-colors ${
      isDark ? 'border-white/[0.04] bg-white/[0.08]' : 'border-slate-200 dark:border-transparent bg-slate-100/50'
    }`}>
      <p className={`text-sm leading-6 ${isDark ? 'text-white/72' : 'text-slate-600'}`}>{context.intro}</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {context.prompts.map((prompt: string) => (
          <button
            key={prompt}
            type="button"
            onClick={() => void submitQuestion(prompt)}
            className={`rounded-full border px-3 py-2 text-xs font-semibold transition ${
              isDark 
                ? 'border-white/[0.05] bg-white/[0.09] text-white/78 hover:bg-white/[0.14] hover:text-white' 
                : 'border-slate-300 dark:border-transparent bg-white text-slate-700 hover:bg-slate-50 hover:text-google-blue hover:border-google-blue'
            } shadow-sm hover:translate-y-[-2px]`}
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );

  const conversationPane = (
    <div className="flex min-h-0 flex-1 flex-col">
      <div 
        ref={scrollRef}
        className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5 custom-scroll"
      >
        {currentMessages.length === 0 ? (
          suggestionPanel
        ) : (
          <>
            {currentMessages.map((message) => (
              <MessageBubble key={message.id} message={message} isDark={isDark} />
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className={`rounded-[1.4rem] border px-4 py-3 backdrop-blur-xl ${
                  isDark ? 'border-white/[0.04] bg-white/[0.08]' : 'border-slate-200 dark:border-transparent bg-slate-100/40'
                }`}>
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 animate-bounce rounded-full ${isDark ? 'bg-fuchsia-400' : 'bg-google-blue'}`} />
                    <span className={`h-2 w-2 animate-bounce rounded-full ${isDark ? 'bg-cyan-400' : 'bg-google-red'} [animation-delay:120ms]`} />
                    <span className={`h-2 w-2 animate-bounce rounded-full ${isDark ? 'bg-violet-400' : 'bg-google-yellow'} [animation-delay:240ms]`} />
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div className={`px-5 py-4 transition-colors ${
        isDark ? 'border-t border-white/[0.03]' : 'border-t border-slate-200 dark:border-transparent bg-slate-50/50'
      }`}>
        <form
          className={`relative p-0 transition-all ${
            isDark 
              ? 'bg-transparent text-white' 
              : 'bg-transparent text-slate-900'
          }`}
          onSubmit={(event) => {
            event.preventDefault();
            void submitQuestion(draft);
          }}
        >
          <div className="flex items-end gap-3">
            <button
              type="button"
              className={`inline-flex h-11 w-11 items-center justify-center rounded-full transition ${
                isDark ? 'bg-white/[0.1] text-white/78 hover:bg-white/[0.16]' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
              }`}
              aria-label="Quick actions"
            >
              <AppIcon name="smart_toy" className="h-5 w-5" />
            </button>

            <div className="flex-1 pb-1">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void submitQuestion(draft);
                  }
                }}
                rows={assistantState.view === 'compact' ? 2 : 3}
                placeholder="Ask anything..."
                className={`w-full resize-none border-none bg-transparent px-2 text-[15px] leading-7 outline-none ring-0 focus:ring-0 transition-colors ${
                  isDark ? 'text-white/90 placeholder:text-white/30' : 'text-slate-900 placeholder:text-slate-400'
                }`}
              />
            </div>

            <button
              type="submit"
              disabled={loading || !draft.trim()}
              className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-gradient-to-br from-[#7b72f2] via-[#a48cff] to-[#efbccf] text-white shadow-[0_16px_28px_rgba(123,114,242,0.24)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:bg-slate-700"
            >
              <AppIcon name="arrow_forward" className="h-4 w-4" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );

  const evidencePane = (
    <aside className={`max-h-full overflow-y-auto custom-scroll border-t px-5 py-5 backdrop-blur-xl lg:border-l lg:border-t-0 transition-colors ${

      isDark ? 'border-white/[0.03] bg-white/[0.05]' : 'border-slate-200 dark:border-transparent bg-slate-50/80'
    }`}>
      <div className="flex items-center gap-2">
        <AppIcon name="memory" className={`h-4 w-4 ${isDark ? 'text-white/62' : 'text-slate-400'}`} />
        <p className={`text-[10px] font-bold uppercase tracking-[0.24em] ${
          isDark ? 'text-white/42' : 'text-slate-500'
        }`}>
          Retrieved evidence
        </p>
      </div>
      <div className="mt-4 space-y-3 pb-4">
        {sourceCards.map((source) => (
          <SourceCard key={`${source.tag}-${source.title}`} source={source} isDark={isDark} />
        ))}
      </div>
    </aside>
  );

  if (isAssessment) return null;

  return (
    <>
      <AnimatePresence>
        {!assistantState.isOpen && (
          <Motion.button
            initial={reduceMotion ? undefined : { opacity: 0, y: 18, scale: 0.96 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: 18, scale: 0.96 }}
            transition={sharedSpring}
            onClick={() =>
              setAssistantState((current) => ({ ...current, isOpen: true, view: 'compact' }))
            }
            onMouseEnter={() => setIsLauncherHovered(true)}
            onMouseLeave={() => setIsLauncherHovered(false)}
            aria-label="Open RAG chat bot"
            className={`fixed bottom-6 right-6 z-[70] flex h-16 items-center overflow-hidden rounded-full border text-left backdrop-blur-[20px] transition-[width,transform,background-color,border-color] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] hover:-translate-y-1 ${
              isDark
                ? 'border-white/[0.05] bg-[rgba(10,10,12,0.86)] shadow-[0_22px_60px_rgba(0,0,0,0.42)]'
                : 'border-slate-200 bg-white/96 shadow-[0_22px_60px_rgba(15,23,42,0.14)]'
            }`}
            style={{ width: isLauncherHovered ? 'min(92vw, 20rem)' : '4rem' }}
          >
            <div className="relative flex w-full items-center gap-4">
              <div className="flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-full bg-google-blue text-white shadow-[0_8px_30px_rgba(66,133,244,0.4)] border-none">
                <AppIcon name="forum" className="h-8 w-8" />
              </div>
              <Motion.div
                animate={
                  reduceMotion
                    ? undefined
                    : {
                        opacity: isLauncherHovered ? 1 : 0,
                        x: isLauncherHovered ? 0 : 14,
                      }
                }
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                className="flex min-w-0 flex-1 items-center justify-between pr-3"
              >
                <p
                  className={`truncate text-xs font-semibold uppercase tracking-[0.24em] ${
                    isDark ? 'text-white/86' : 'text-slate-700'
                  }`}
                >
                  RAG CHAT BOT
                </p>
                <AppIcon
                  name="arrow_forward"
                  className={`h-4 w-4 flex-shrink-0 ${isDark ? 'text-white/52' : 'text-slate-400'}`}
                />
              </Motion.div>
            </div>
          </Motion.button>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {assistantState.isOpen && assistantState.view !== 'compact' && (
          <Motion.div
            initial={reduceMotion ? undefined : { opacity: 0 }}
            animate={reduceMotion ? undefined : { opacity: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0 }}
            className="fixed inset-0 z-[64] bg-black/16 backdrop-blur-[4px]"
            onClick={() => {
              if (assistantState.view === 'full') {
                closeAssistant();
              }
            }}
          />
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {assistantState.isOpen && assistantState.view === 'compact' && (
          <Motion.section
            key="assistant-compact"
            initial={reduceMotion ? undefined : { opacity: 0, y: 18, scale: 0.98 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: 18, scale: 0.98 }}
            transition={sharedSpring}
            className="fixed bottom-6 right-6 z-[70] h-[39rem] w-[min(96vw,28rem)]"
          >
            <AssistantShell isDark={isDark} className="h-full rounded-[2rem]">
              {sharedHeader}
              {conversationPane}
            </AssistantShell>
          </Motion.section>
        )}

        {assistantState.isOpen && assistantState.view === 'sidebar' && (
          <Motion.section
            key="assistant-sidebar"
            initial={reduceMotion ? undefined : { opacity: 0, x: 28 }}
            animate={reduceMotion ? undefined : { opacity: 1, x: 0 }}
            exit={reduceMotion ? undefined : { opacity: 0, x: 28 }}
            transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] as const }}
            className="fixed bottom-6 right-6 top-[5.6rem] z-[70] w-[min(94vw,28rem)]"
          >
            <AssistantShell isDark={isDark} className="flex h-full flex-col rounded-[2rem]">
              {sharedHeader}
              {conversationPane}
              {evidencePane}
            </AssistantShell>
          </Motion.section>
        )}

        {assistantState.isOpen && assistantState.view === 'full' && (
          <Motion.section
            key="assistant-full"
            initial={reduceMotion ? undefined : { opacity: 0, y: 18, scale: 0.985 }}
            animate={reduceMotion ? undefined : { opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: 18, scale: 0.985 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] as const }}
            className="fixed bottom-4 left-4 right-4 top-[5.5rem] z-[70] lg:left-[calc(var(--dashboard-sidebar-width)+1rem)]"
          >
            <AssistantShell isDark={isDark} className="h-full rounded-[2.25rem]">
              {sharedHeader}
              <div className="grid h-[calc(100%-5.4rem)] min-h-0 lg:grid-cols-[minmax(0,1.35fr)_23rem]">
                {conversationPane}
                {evidencePane}
              </div>
            </AssistantShell>
          </Motion.section>
        )}
      </AnimatePresence>
    </>
  );
};

export default WorkspaceCopilot;
