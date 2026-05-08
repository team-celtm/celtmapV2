"use client";

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion as Motion, useReducedMotion } from 'framer-motion';
import AppIcon from '../components/AppIcon';
import CeltmLogo from '../components/CeltmLogo';
import { useTheme } from '../contexts/ThemeContext';

const engineer = '/landing/engineer.png';
const scientist = '/landing/scientist.png';
const fullstack = '/landing/fullstack.png';
const product = '/landing/product.png';
const architect = '/landing/architect.png';
const backend = '/landing/backend.png';
const designer = '/landing/designer.png';
const security = '/landing/security.png';
const marketing = '/landing/marketing.png';
const featurePerson1 = '/landing/feature-person1.png';
const featurePerson2 = '/landing/feature-person2.png';
const course1 = '/landing/course1.jpg';
const course2 = '/landing/course2.jpg';
const course3 = '/landing/course3.jpg';

const heroProfiles = [
  { image: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=800&auto=format&fit=crop", name: "Marcus", role: "Data Scientist", accent: "bg-google-blue" },
  { image: "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?q=80&w=800&auto=format&fit=crop", name: "Ava", role: "Lead ML Engineer", accent: "bg-google-red" },
  { image: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?q=80&w=800&auto=format&fit=crop", name: "Chen", role: "Fullstack Dev", accent: "bg-google-yellow" },
  { image: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?q=80&w=800&auto=format&fit=crop", name: "Elena", role: "Product Lead", accent: "bg-google-green" },
  { image: "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?q=80&w=800&auto=format&fit=crop", name: "David", role: "Cloud Architect", accent: "bg-google-blue" },
  { image: "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?q=80&w=800&auto=format&fit=crop", name: "Sarah", role: "Backend Dev", accent: "bg-google-red" },
  { image: "https://images.unsplash.com/photo-1580489944761-15a19d654956?q=80&w=800&auto=format&fit=crop", name: "Leo", role: "Product Designer", accent: "bg-google-yellow" },
  { image: "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?q=80&w=800&auto=format&fit=crop", name: "Maya", role: "Security Auditor", accent: "bg-google-green" },
  { image: "https://images.unsplash.com/photo-1544005313-94ddf0286df2?q=80&w=800&auto=format&fit=crop", name: "James", role: "Marketing Analyst", accent: "bg-google-blue" },
];

const platformCards = [
  {
    image: course1,
    title: 'Skill Intelligence Dashboard',
    body: 'Readiness, role-fit, and folio movement come together in one calm overview.',
    chip: 'Live signal',
    accent: 'bg-google-red',
  },
  {
    image: course2,
    title: 'Adaptive Interview Studio',
    body: 'Practice with structure, review with clarity, and surface stronger evidence faster.',
    chip: 'Mock workspace',
    accent: 'bg-google-blue',
  },
  {
    image: course3,
    title: 'AI-Powered Learning Path',
    body: 'Turn gaps from real sessions into targeted next steps instead of generic training.',
    chip: 'Next actions',
    accent: 'bg-google-green',
  },
];

const featureRows = [
  {
    badge: 'Current Product',
    title: 'One connected practice flow from dashboard intelligence to portfolio improvement.',
    body:
      'CELTM connects interviews, sessions, learning paths, and competency shifts so users can see what improved, what still needs work, and what belongs in the folio next.',
    image: featurePerson1,
    imageTone: 'bg-[#ccb9ff]',
    reverse: false,
  },
  {
    badge: 'Website Direction',
    title: 'From potential to performance, made measurable with context.',
    body:
      'The platform is designed around CELTM’s model of potential, readiness, and context. That means the next best action is tied to evidence, not intuition alone.',
    image: featurePerson2,
    imageTone: 'bg-[#7fe0c5]',
    reverse: true,
  },
];

const ecosystemCards = [
  {
    title: 'Progressive Colleges',
    body: 'Institutions reimagining placement outcomes and real-world skill readiness.',
    badge: 'Placement signal',
  },
  {
    title: 'Future-Ready Businesses',
    body: 'Teams prioritizing validated capability, adaptability, and intelligence.',
    badge: 'Talent discovery',
  },
  {
    title: 'Innovation-Driven Policymakers',
    body: 'Leaders building scalable, skills-based workforce systems with better data.',
    badge: 'Regional systems',
  },
  {
    title: 'Strategic Partners',
    body: 'Collaborators shaping national talent ecosystems around clearer employability proof.',
    badge: 'Long-horizon growth',
  },
];

const faqs = [
  {
    question: 'What does CELTM actually help users do?',
    answer:
      'CELTM helps users practice, track readiness, improve targeted skills, and translate progress into clearer employability and folio proof.',
  },
  {
    question: 'How is this different from generic interview prep?',
    answer:
      'The workflow is connected. Interview sessions, competency movement, role fit, and learning paths all feed each other rather than living in separate tools.',
  },
  {
    question: 'Who is CELTM built for?',
    answer:
      'It is built for institutions, teams, and individuals working on measurable skill growth, stronger talent discovery, and better deployment decisions.',
  },
  {
    question: 'What is the core model behind the platform?',
    answer:
      'CELTM’s direction combines potential, readiness, and context to move from knowledge toward measurable employability.',
  },
];

const reveal = {
  hidden: { opacity: 0, y: 28 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.78, ease: [0.22, 1, 0.36, 1] as const },
  },
};

const Marquee = ({ words }: { words: string[] }) => (
  <div className="flex overflow-hidden whitespace-nowrap py-12 bg-slate-900/5 border-y border-slate-900/10 dark:border-transparent">
    <Motion.div
      initial={{ x: "-50%" }}
      animate={{ x: 0 }}
      transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
      className="flex gap-12 items-center"
    >
      {[...words, ...words].map((word, i) => (
        <span key={i} className="text-4xl md:text-6xl font-black italic tracking-tighter text-slate-900/20 px-4 uppercase">
          {word}
        </span>
      ))}
    </Motion.div>
  </div>
);

const ProfileMarquee = ({ profiles }: { profiles: typeof heroProfiles }) => (
  <div className="flex overflow-hidden whitespace-nowrap py-14 w-full">
    <Motion.div
      initial={{ x: 0 }}
      animate={{ x: "-50%" }}
      transition={{ duration: 45, repeat: Infinity, ease: "linear" }}
      className="flex gap-8 items-center px-4"
    >
      {[...profiles, ...profiles].map((profile, i) => (
        <div 
          key={i} 
          className="relative h-72 w-96 shrink-0 overflow-hidden rounded-[2.5rem] bg-white shadow-xl border border-slate-100 dark:border-transparent group transition-transform hover:scale-[1.05] hover:z-20 cursor-default"
        >
          <img 
            src={profile.image} 
            alt={profile.name} 
            className="h-full w-full object-cover transition-all duration-500 group-hover:scale-110"
          />
          <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent p-6 text-white group-hover:from-black/90 transition-all">
            <p className="text-xl font-black text-white">{profile.name}</p>
            <p className="text-sm text-google-blue font-bold tracking-wide">{profile.role}</p>
          </div>
          <div className={`absolute top-4 right-4 h-10 w-10 rounded-full ${profile.accent} border-4 border-white shadow-lg group-hover:scale-110 transition-transform`} />
        </div>
      ))}
    </Motion.div>
  </div>
);

export default function LandingPage() {
  const { theme, toggleTheme } = useTheme();
  const reduceMotion = useReducedMotion();
  const [isScrolled, setIsScrolled] = useState(false);
  const [openFaq, setOpenFaq] = useState(0);
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
    const onScroll = () => setIsScrolled(window.scrollY > 18);
    onScroll();
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  if (!isClient) {
    return <div className="min-h-screen bg-[#fbf6f0] dark:bg-[#0d1221]" />;
  }

  return (
    <div className="min-h-screen bg-[#fbf6f0] text-slate-950 transition-colors duration-300">
      <Motion.nav
        initial={reduceMotion ? undefined : { opacity: 0, y: -18 }}
        animate={reduceMotion ? undefined : { opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className={`fixed inset-x-0 top-0 z-40 transition-all duration-500 ${
          isScrolled
            ? 'border-b border-[#e9dfd5] bg-[#fbf6f0]/86 shadow-[0_18px_44px_rgba(131,108,87,0.08)] backdrop-blur-xl'
            : 'bg-transparent'
        }`}
      >
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-5 md:px-8">
          <Link href="/" className="inline-flex items-center">
            <CeltmLogo className="h-12 text-slate-900" />
          </Link>

          <div className="flex items-center gap-4">
            <Motion.div
              whileHover={reduceMotion ? undefined : { y: -2 }}
              whileTap={reduceMotion ? undefined : { scale: 0.985 }}
            >
              <Link
                href="/login"
                className="inline-flex items-center rounded-full bg-google-blue px-6 py-3 text-sm font-semibold text-white shadow-[0_22px_46px_rgba(66,133,244,0.26)] transition hover:brightness-110"
              >
                Enter Login Page
              </Link>
            </Motion.div>
          </div>
        </div>
      </Motion.nav>

      <main>
        <section className="relative overflow-hidden px-5 pb-0 pt-28 md:px-8 md:pt-32">
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute left-[-4rem] top-10 h-56 w-56 rounded-full bg-[#ffc5b5]/45 blur-[110px]" />
            <div className="absolute right-[-4rem] top-16 h-72 w-72 rounded-full bg-[#bfd1ff]/55 blur-[125px]" />
          </div>

          <div className="mx-auto max-w-6xl">
            <Motion.div
              variants={reveal}
              initial="hidden"
              animate="visible"
              className="mx-auto max-w-5xl text-center"
            >
              <p className="mb-5 inline-flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-[#6d7aa6] shadow-sm">
                <AppIcon name="auto_awesome" className="h-4 w-4" />
                Designed for long-horizon capability systems
              </p>

              <h1 className="landing-editorial mx-auto max-w-5xl text-5xl font-bold leading-[0.98] tracking-tight text-slate-950 sm:text-6xl lg:text-8xl">
                What if talent could
                <br />
                <span className="relative inline-block">
                  speak for itself?
                  <Motion.svg
                    initial={reduceMotion ? undefined : { pathLength: 0, opacity: 0 }}
                    animate={reduceMotion ? undefined : { pathLength: 1, opacity: 1 }}
                    transition={{ delay: 0.45, duration: 0.9, ease: 'easeOut' }}
                    className="absolute -bottom-2 left-2 h-4 w-[92%]"
                    viewBox="0 0 240 20"
                    fill="none"
                  >
                    <path
                      d="M4 13C64 4 176 4 236 14"
                      stroke="#ff8b96"
                      strokeWidth="5"
                      strokeLinecap="round"
                    />
                  </Motion.svg>
                </span>
              </h1>

              <p className="mx-auto mt-7 max-w-3xl text-lg leading-8 text-slate-600">
                We built the system that listens. CELTM is building a skill-based intelligence
                layer that helps users discover who&apos;s ready, develop who&apos;s rising, and
                deploy who matters.
              </p>

              <div className="mt-9 flex flex-wrap items-center justify-center gap-4">
                <Motion.div
                  whileHover={reduceMotion ? undefined : { y: -3, scale: 1.02 }}
                  whileTap={reduceMotion ? undefined : { scale: 0.98 }}
                >
                  <Link
                    href="/login"
                    className="inline-flex items-center gap-2 rounded-full bg-google-blue px-7 py-4 text-sm font-semibold text-white shadow-[0_20px_46px_rgba(66,133,244,0.26)] transition hover:brightness-110"
                  >
                    Launch CELTM
                    <AppIcon name="arrow_forward" className="h-4 w-4" />
                  </Link>
                </Motion.div>

                <Motion.div
                  whileHover={reduceMotion ? undefined : { y: -3 }}
                  whileTap={reduceMotion ? undefined : { scale: 0.98 }}
                >
                  <a
                    href="#platform"
                    className="inline-flex items-center gap-2 rounded-full border border-[#e4d8cb] bg-white/90 px-7 py-4 text-sm font-semibold text-slate-700 transition hover:border-[#cfd5ff] hover:text-[#4961ff]"
                  >
                    See the platform
                  </a>
                </Motion.div>
              </div>
            </Motion.div>

          </div>
          
          <div className="mt-14 w-screen relative left-1/2 -translate-x-1/2">
            <ProfileMarquee profiles={heroProfiles} />
          </div>
        </section>

        <div className="bg-white py-12">
          <Marquee words={["Authentic Performance", "Measurable Growth", "Deployable Ready", "Future Skills"]} />
        </div>

        <section className="relative overflow-hidden bg-[#fffdf9] px-5 py-20 md:px-8 -mt-20">
          <div className="absolute top-0 left-0 right-0 h-[600px] bg-google-red z-0">
            <svg viewBox="0 0 1440 120" preserveAspectRatio="none" fill="none" className="absolute top-0 left-0 w-full h-32 -translate-y-full">
              <path d="M0 60C240 110 480 20 720 65C960 105 1200 25 1440 65V121H0V60Z" fill="#EA4335" />
            </svg>
            <svg viewBox="0 0 1440 100" preserveAspectRatio="none" fill="none" className="absolute bottom-0 left-0 w-full h-24 translate-y-full">
               <path d="M0 44C360 90 720 10 1080 44C1260 60 1380 85 1440 85V100H0V44Z" fill="#EA4335" />
            </svg>
          </div>

          <div className="mx-auto grid max-w-6xl gap-12 lg:grid-cols-[1.15fr_0.85fr] lg:items-start relative z-10">
            <Motion.div
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, amount: 0.3 }}
              variants={reveal}
              className="text-slate-950"
            >
              <p className="mb-5 inline-flex rounded-full border border-slate-950/18 dark:border-transparent px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-900/70">
                The New Talent Equation
              </p>
              <h2 className="landing-editorial max-w-4xl text-4xl font-bold leading-[1.08] md:text-6xl">
                From potential to performance, made measurable.
              </h2>
              <p className="mt-6 max-w-2xl text-base leading-8 text-slate-900/72">
                CELTM works at the intersection of capability, readiness, and opportunity. The
                goal is not generic training. It is measurable workforce progress that can be
                surfaced, developed, and deployed with more clarity.
              </p>
            </Motion.div>

            <Motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.75, ease: [0.22, 1, 0.36, 1] }}
              className="space-y-4"
            >
              {[
                ['Potential', 'Innate capability and learning capacity'],
                ['Readiness', 'Current skill level and preparedness'],
                ['Context', 'Market demand and deployable fit'],
                ['True Employability', 'A clearer signal of who is ready now'],
              ].map(([title, body], index) => (
                <Motion.div
                  key={title}
                  whileHover={{ 
                    scale: 1.03, 
                    backgroundColor: '#ffffff',
                    boxShadow: '0 20px 40px rgba(0,0,0,0.1)',
                    transition: { duration: 0.2, ease: "easeOut" }
                  }}
                  transition={{
                    duration: 0.5,
                    delay: index * 0.05,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                  className="group cursor-pointer rounded-[2.2rem] border border-slate-950/10 dark:border-transparent bg-white/90 p-6 shadow-[0_16px_34px_rgba(138,85,63,0.12)] backdrop-blur-md will-change-transform"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="flex-1">
                      <p className="text-xl font-black text-slate-950 group-hover:text-google-blue transition-colors">{title}</p>
                      <p className="mt-1.5 text-sm leading-6 text-slate-700 font-medium">{body}</p>
                    </div>
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 border-slate-950/12 dark:border-transparent bg-white text-slate-800 shadow-sm group-hover:border-google-blue group-hover:text-google-blue group-hover:rotate-12 transition-all duration-300">
                      <span className="text-xl font-bold">{index < 3 ? '×' : '='}</span>
                    </div>
                  </div>
                </Motion.div>
              ))}
            </Motion.div>
          </div>
        </section>

        <section id="platform" className="bg-[#fffdf9] px-5 py-20 md:px-8">
          <div className="mx-auto max-w-6xl">
            <Motion.div
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, amount: 0.25 }}
              variants={reveal}
              className="mb-10 flex flex-col gap-6 md:flex-row md:items-end md:justify-between"
            >
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#7280ad]">
                  Inside CELTM
                </p>
                <h2 className="landing-editorial mt-3 text-4xl font-bold leading-tight text-slate-950 md:text-6xl">
                  Build skill signals with a cleaner, calmer product flow.
                </h2>
              </div>
              <a
                href="#stories"
                className="inline-flex items-center gap-2 self-start rounded-full border border-[#e7dbcf] px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-[#cfd5ff] hover:text-[#4961ff]"
              >
                See product stories
                <AppIcon name="arrow_forward" className="h-4 w-4" />
              </a>
            </Motion.div>

            <div className="grid gap-6 lg:grid-cols-3">
              {platformCards.map((card, index) => (
                <Motion.article
                  key={card.title}
                  initial={{ opacity: 0, y: 34 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.25 }}
                  transition={{
                    duration: 0.72,
                    delay: index * 0.08,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                  whileHover={reduceMotion ? undefined : { y: -8 }}
                  className="overflow-hidden rounded-[2rem] bg-[#15131f] text-white shadow-[0_24px_56px_rgba(20,16,31,0.18)]"
                >
                  <div className="h-64 overflow-hidden">
                    <img
                      src={card.image}
                      alt={card.title}
                      className="h-full w-full object-cover transition duration-500 hover:scale-[1.04]"
                      loading="lazy"
                    />
                  </div>
                  <div className="space-y-4 p-6">
                    <span className={`inline-flex rounded-full px-4 py-1.5 text-xs font-semibold text-slate-950 ${card.accent}`}>
                      {card.chip}
                    </span>
                    <h3 className="landing-editorial text-3xl font-bold leading-tight">{card.title}</h3>
                    <p className="text-sm leading-7 text-white/72">{card.body}</p>
                  </div>
                </Motion.article>
              ))}
            </div>
          </div>
        </section>

        <section id="stories" className="bg-[#fffdf9] px-5 pb-20 md:px-8">
          <div className="mx-auto max-w-6xl space-y-20">
            {featureRows.map((row) => (
              <Motion.div
                key={row.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.25 }}
                transition={{ duration: 0.78, ease: [0.22, 1, 0.36, 1] }}
                className={`grid gap-12 md:grid-cols-2 md:items-center ${
                  row.reverse ? 'md:[&>*:first-child]:order-2' : ''
                }`}
              >
                <div className="space-y-5">
                  <span className="inline-flex rounded-full bg-[#e8ddff] px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.22em] text-[#5b57bf]">
                    {row.badge}
                  </span>
                  <h2 className="landing-editorial text-4xl font-bold leading-tight text-slate-950 md:text-5xl">
                    {row.title}
                  </h2>
                  <p className="max-w-xl text-base leading-8 text-slate-600">
                    {row.body}
                  </p>
                </div>

                <div className="flex justify-center">
                  <div
                    className={`relative h-[27rem] w-full max-w-[28rem] overflow-hidden rounded-[2.4rem] ${row.imageTone} shadow-[0_22px_56px_rgba(116,96,85,0.14)]`}
                  >
                    <img
                      src={row.image}
                      alt={row.title}
                      className="h-full w-full object-cover object-top"
                      loading="lazy"
                    />
                  </div>
                </div>
              </Motion.div>
            ))}
          </div>
        </section>

        <section className="relative overflow-hidden bg-[#fffdf9] px-5 py-20 md:px-8 mt-20">
          <div className="absolute top-0 left-0 right-0 h-[500px] bg-google-green z-0">
            <svg viewBox="0 0 1440 100" preserveAspectRatio="none" fill="none" className="absolute top-0 left-0 w-full h-24 -translate-y-[95%]">
               <path d="M0 44C360 90 720 10 1080 44C1260 60 1380 85 1440 85V100H0V44Z" fill="#34A853" className="rotate-180 origin-center" />
            </svg>
            <svg viewBox="0 0 1440 100" preserveAspectRatio="none" fill="none" className="absolute bottom-0 left-0 w-full h-24 translate-y-[95%]">
               <path d="M0 44C360 90 720 10 1080 44C1260 60 1380 85 1440 85V100H0V44Z" fill="#34A853" />
            </svg>
          </div>

          <div className="mx-auto grid max-w-6xl gap-12 md:grid-cols-[0.9fr_1.1fr] relative z-10">
            <Motion.div
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, amount: 0.25 }}
              variants={reveal}
            >
              <h2 className="landing-editorial text-4xl font-bold leading-tight text-slate-950 md:text-6xl">
                Who we work with shapes how the product scales.
              </h2>
              <p className="mt-5 max-w-md text-base leading-8 text-slate-900/72">
                CELTM is built for institutions, teams, and ecosystem builders who want talent
                decisions to be grounded in signal, growth, and context.
              </p>
              <Link
                href="/login"
                className="mt-7 inline-flex rounded-full border border-slate-950/18 dark:border-transparent px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-white/30"
              >
                Enter the workspace
              </Link>
            </Motion.div>

            <div className="space-y-4">
              {ecosystemCards.map((card, index) => (
                <Motion.div
                  key={card.title}
                  initial={{ opacity: 0, y: 32 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.25 }}
                  whileHover={{ 
                    scale: 1.025, 
                    backgroundColor: '#ffffff',
                    boxShadow: '0 20px 50px rgba(0,0,0,0.08)',
                    transition: { duration: 0.2, ease: "easeOut" }
                  }}
                  transition={{
                    duration: 0.6,
                    delay: index * 0.1,
                    ease: [0.22, 1, 0.36, 1],
                  }}
                  className="group flex cursor-pointer items-center gap-6 rounded-[2.25rem] border border-white/40 bg-white/94 p-6 shadow-[0_20px_40px_rgba(33,56,51,0.08)] backdrop-blur-md will-change-transform"
                >
                  <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-google-blue to-google-red text-white shadow-lg transition-transform group-hover:rotate-6">
                    <AppIcon
                      name={index === 0 ? 'school' : index === 1 ? 'architecture' : index === 2 ? 'language' : 'hub'}
                      className="h-7 w-7"
                    />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xl font-black text-slate-950 transition-colors group-hover:text-google-blue">
                        {card.title}
                      </p>
                      <span className="hidden rounded-full border border-slate-950/8 dark:border-transparent bg-slate-950/4 px-3 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-slate-600 sm:block">
                        {card.badge}
                      </span>
                    </div>
                    <p className="mt-1.5 text-sm leading-6 font-medium text-slate-600">
                      {card.body}
                    </p>
                  </div>
                </Motion.div>
              ))}
            </div>
          </div>

          <div className="absolute bottom-0 left-0 right-0 -mb-1 translate-y-1">
            <svg viewBox="0 0 1440 100" preserveAspectRatio="none" fill="none" className="w-full h-24 scale-x-110 origin-center">
              <path d="M0 0C360 65 720 0 1080 44C1260 62 1440 44 1440 44V101H0V0Z" fill="white" />
            </svg>
          </div>
        </section>

        <section className="bg-white px-5 py-20 md:px-8">
          <div className="mx-auto max-w-3xl">
            <Motion.div
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, amount: 0.25 }}
              variants={reveal}
              className="text-center"
            >
              <h2 className="landing-editorial text-4xl font-bold leading-tight text-slate-950 md:text-6xl">
                Frequently asked questions
              </h2>
            </Motion.div>

            <div className="mt-10 space-y-4">
              {faqs.map((faq, index) => {
                const isOpen = openFaq === index;

                return (
                  <Motion.div
                    key={faq.question}
                    initial={{ opacity: 0, y: 22 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, amount: 0.25 }}
                    transition={{
                      duration: 0.65,
                      delay: index * 0.06,
                      ease: [0.22, 1, 0.36, 1],
                    }}
                    className={`overflow-hidden border border-[#eadfd4] bg-white/88 transition-all ${
                      isOpen ? 'rounded-[2rem]' : 'rounded-full'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => setOpenFaq(isOpen ? -1 : index)}
                      className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left"
                    >
                      <span className="text-sm font-semibold text-slate-950 md:text-base">
                        {faq.question}
                      </span>
                      <span className="flex h-8 w-8 items-center justify-center rounded-full border border-slate-300 dark:border-transparent text-slate-700">
                        {isOpen ? '−' : '+'}
                      </span>
                    </button>
                    {isOpen && (
                      <div className="px-6 pb-5 text-sm leading-7 text-slate-600">
                        {faq.answer}
                      </div>
                    )}
                  </Motion.div>
                );
              })}
            </div>
          </div>
        </section>

        <section className="bg-surface px-5 pb-20 md:px-8">
          <div className="mx-auto max-w-6xl rounded-[2.6rem] bg-google-blue px-6 py-14 text-center text-white shadow-[0_26px_70px_rgba(66,133,244,0.3)] md:px-12 md:py-16">
            <Motion.div
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true, amount: 0.25 }}
              variants={reveal}
            >
              <h2 className="landing-editorial text-4xl font-bold leading-tight md:text-6xl">
                Join CELTM and grow stronger skill signals.
              </h2>
              <p className="mx-auto mt-5 max-w-2xl text-base leading-8 text-white/78">
                Practice smarter, track readiness shifts, and turn better sessions into clearer
                portfolio evidence inside the workspace.
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
                <Link
                  href="/login"
                  className="rounded-full bg-white px-7 py-4 text-sm font-semibold text-[#4961ff] transition hover:bg-[#f4f6ff]"
                >
                  Enter Login Page
                </Link>
                <a
                  href="https://www.celtm.com/"
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-full border border-white/24 px-7 py-4 text-sm font-semibold text-white transition hover:bg-white/10"
                >
                  Visit CELTM website
                </a>
              </div>
            </Motion.div>
          </div>
        </section>
      </main>

      <footer className="border-t border-[#eadfd4] bg-[#fffdf9] px-5 py-10 md:px-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-8 md:flex-row md:items-start md:justify-between">
          <div className="max-w-md">
            <CeltmLogo className="h-11 text-slate-900" />
            <p className="mt-4 text-sm leading-7 text-slate-600">
              CELTM works at the intersection of capability, readiness, and opportunity, helping
              institutions, organizations, and individuals engage with more clarity and purpose.
            </p>
          </div>

          <div className="grid gap-8 sm:grid-cols-2">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">
                Contact
              </p>
              <div className="mt-4 space-y-2 text-sm text-slate-600">
                <p>+91 079-45930555</p>
                <p>team@celtm.com</p>
              </div>
            </div>

            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-400">
                Address
              </p>
              <div className="mt-4 space-y-2 text-sm text-slate-600">
                <p>E-704, Titanium City Center</p>
                <p>Nr Income Tax Office, Satellite</p>
                <p>Ahmedabad - 380015</p>
              </div>
            </div>
          </div>
        </div>

        <div className="mx-auto mt-8 flex max-w-6xl flex-col gap-3 border-t border-[#eadfd4] pt-6 text-xs text-slate-500 md:flex-row md:items-center md:justify-between">
          <span>(c) 2026 CELTM Global Pvt Ltd. All rights reserved.</span>
          <span>Designed for long-horizon capability systems.</span>
        </div>
      </footer>
    </div>
  );
}
