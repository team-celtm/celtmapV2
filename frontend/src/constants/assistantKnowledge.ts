interface AssistantSource {
  title: string;
  detail: string;
  tag: string;
}

interface AssistantContextData {
  title: string;
  intro: string;
  nextAction: string;
  prompts: string[];
  sources: AssistantSource[];
}

type AssistantKnowledgeMap = Record<string, AssistantContextData> & {
  default: AssistantContextData;
};

export const assistantKnowledge: AssistantKnowledgeMap = {
  '/dashboard': {
    title: 'Practice Overview',
    intro:
      'Readiness is climbing steadily, with communication structure and system framing doing most of the lifting.',
    nextAction:
      'Run one deployment-heavy mock and convert two recent wins into folio proof points.',
    prompts: [
      'What should I do next this week?',
      'Summarize my readiness in one view.',
      'Where is my biggest improvement opportunity?',
    ],
    sources: [
      {
        title: 'Readiness trend',
        detail: 'Your readiness moved from 51% to 78% across the last six checkpoints.',
        tag: 'Trend',
      },
      {
        title: 'Best signal',
        detail: 'Structured communication is currently the most reliable differentiator.',
        tag: 'Strength',
      },
      {
        title: 'Folio lift',
        detail: 'Two captured wins could improve portfolio clarity by about 8%.',
        tag: 'Folio',
      },
    ],
  },
  '/interview': {
    title: 'Interview Copilot',
    intro:
      'The strongest answers in this workspace start with the latency or system constraint, then walk into tradeoffs and validation.',
    nextAction:
      'Anchor the answer in a deployment scenario, then explain quantization, batching, and evaluation order.',
    prompts: [
      'How should I structure this answer?',
      'What is the strongest next sentence?',
      'Which gap should I correct before submitting?',
    ],
    sources: [
      {
        title: 'Context hint',
        detail: 'Latency budget and hardware-aware tradeoffs matter more than listing optimizations generically.',
        tag: 'Hint',
      },
      {
        title: 'Source cue',
        detail: 'Kernel fusion and mixed precision remove repeated memory-bound overhead.',
        tag: 'Evidence',
      },
      {
        title: 'Answer pattern',
        detail: 'Start with objective, move into constraints, then close with validation metrics.',
        tag: 'Pattern',
      },
    ],
  },
  '/learning-path': {
    title: 'Roadmap Guide',
    intro:
      'The roadmap is optimized around statistical rigor, supervised learning systems, and deployment clarity.',
    nextAction:
      'Complete the active supervised learning block and tie each concept to one practical example.',
    prompts: [
      'What module has the highest leverage?',
      'How do I finish the current block faster?',
      'Which topic best improves interviews and folio together?',
    ],
    sources: [
      {
        title: 'Current focus',
        detail: 'Supervised learning is the highest-return module for current interview performance.',
        tag: 'Focus',
      },
      {
        title: 'Next unlock',
        detail: 'Bayesian inference still carries the biggest leverage for better explanations.',
        tag: 'Unlock',
      },
      {
        title: 'Completion path',
        detail: 'One explanation-to-example cycle is the cleanest way to finish the active block.',
        tag: 'Path',
      },
    ],
  },
  '/sessions': {
    title: 'Session Analyst',
    intro:
      'Your score rhythm is healthy overall, but the weaker sessions still show the same deployment and experimentation gaps.',
    nextAction:
      'Review the lowest-scoring session first, then compare it to your strongest systems-design rep.',
    prompts: [
      'Which session should I review first?',
      'What pattern repeats in my lower scores?',
      'What moved my best week so high?',
    ],
    sources: [
      {
        title: 'Average score',
        detail: 'Session average is 79%, with the strongest spike coming from system design.',
        tag: 'Score',
      },
      {
        title: 'Repeated weakness',
        detail: 'Deployment-specific examples are still missing in lower-scoring sessions.',
        tag: 'Gap',
      },
      {
        title: 'Consistency note',
        detail: 'Structured reasoning remains stable even when technical depth drops.',
        tag: 'Pattern',
      },
    ],
  },
  '/competency-map': {
    title: 'Competency Intelligence',
    intro:
      'Machine learning, systems, and storytelling form your strongest cluster. Data operations is the only node still suppressing the whole map.',
    nextAction:
      'Raise Ops with one deployment-focused mock and a postmortem review to rebalance the map.',
    prompts: [
      'Explain my weakest edge.',
      'What single competency lifts the whole map?',
      'How should I read the new graphs?',
    ],
    sources: [
      {
        title: 'Top cluster',
        detail: 'ML and Systems are the densest connected strengths in your map.',
        tag: 'Cluster',
      },
      {
        title: 'Weakest edge',
        detail: 'Systems to Ops is only 58%, which is the biggest balancing opportunity.',
        tag: 'Edge',
      },
      {
        title: 'Map score',
        detail: 'Overall competency score sits at 81 with one infrastructure-side gap.',
        tag: 'Score',
      },
    ],
  },
  '/settings': {
    title: 'Workspace Settings',
    intro:
      'This page controls profile, notification, and workspace behavior for the current prototype.',
    nextAction:
      'Keep notifications on for streaks and folio reminders, then save once after all preference changes.',
    prompts: [
      'What settings matter most?',
      'Which reminders should I keep enabled?',
      'How should I configure the workspace for practice?',
    ],
    sources: [
      {
        title: 'Notifications',
        detail: 'Workspace alerts and folio reminders are the highest-value settings here.',
        tag: 'Prefs',
      },
      {
        title: 'Theme',
        detail: 'Theme mode is saved locally and can switch between light and dark at any time.',
        tag: 'Theme',
      },
      {
        title: 'Profile',
        detail: 'Name, goal, and role labels appear across the dashboard surfaces.',
        tag: 'Profile',
      },
    ],
  },
  '/assessment': {
    title: 'Assessment Intelligence',
    intro:
      'Your baseline is strongest in communication and analysis, with SQL depth and industry framing still limiting the overall readiness score.',
    nextAction:
      'Raise the lowest two modules first, then retake the adaptive baseline to refresh your recommendations.',
    prompts: [
      'Which module should I fix first?',
      'Summarize my assessment in one view.',
      'How should I improve the weakest areas fastest?',
    ],
    sources: [
      {
        title: 'Overall readiness',
        detail: 'Current baseline sits at 72%, with communication leading the spread.',
        tag: 'Score',
      },
      {
        title: 'Priority gap',
        detail: 'Industry readiness is the biggest drag on the total signal right now.',
        tag: 'Gap',
      },
      {
        title: 'Next lift',
        detail: 'One SQL tools sprint and one business-context case review create the fastest improvement path.',
        tag: 'Lift',
      },
    ],
  },
  '/hidden-skills': {
    title: 'Hidden Skills Intelligence',
    intro:
      'This page surfaces transfer skills and likely strengths inferred from the way you describe hobbies, side projects, and decision-making patterns in interviews.',
    nextAction:
      'Validate the highest-confidence inferred strengths first, then turn the strongest ones into interview proof points and folio language.',
    prompts: [
      'What hidden skills did the interview reveal?',
      'Which inferred skill should I validate first?',
      'How can I turn these hidden signals into better answers?',
    ],
    sources: [
      {
        title: 'Chess signal',
        detail: 'Statements about chess and structured gameplay suggest tactical reasoning, pattern recognition, and calm decision-making under pressure.',
        tag: 'Inference',
      },
      {
        title: 'Mentoring cue',
        detail: 'Explaining concepts clearly or helping peers often points to coaching ability and communication lift.',
        tag: 'Behavior',
      },
      {
        title: 'Project hobby',
        detail: 'Weekend builds and curiosity-led side work usually map to self-driven learning and systems ownership.',
        tag: 'Potential',
      },
    ],
  },
  '/profile': {
    title: 'User Dashboard',
    intro:
      'This page is strongest for translating progress into a long-term growth story and folio narrative.',
    nextAction:
      'Turn architecture mocks and communication gains into concise proof points this week.',
    prompts: [
      'How do I improve my folio fastest?',
      'What should this page tell recruiters?',
      'Which proof point should I add next?',
    ],
    sources: [
      {
        title: 'Folio score',
        detail: 'Portfolio score is already strong, but missing two high-signal proof points.',
        tag: 'Folio',
      },
      {
        title: 'Next lift',
        detail: 'Architecture stories and deployment examples are ready to publish.',
        tag: 'Lift',
      },
      {
        title: 'Practice narrative',
        detail: 'Communication and systems growth are the clearest parts of your long-term story.',
        tag: 'Narrative',
      },
    ],
  },
  default: {
    title: 'RAG CHAT BOT',
    intro:
      'I can summarize the current dashboard, explain the charts, or turn the strongest signals into next actions.',
    nextAction: 'Ask for a summary, a next step, or a graph explanation.',
    prompts: [
      'Summarize this page.',
      'What should I do next?',
      'Explain the charts here.',
    ],
    sources: [
      {
        title: 'Workspace context',
        detail: 'This assistant reads the current dashboard context and summarizes the strongest signals.',
        tag: 'Context',
      },
    ],
  },
};

export const buildAssistantResponse = (pathname: string, question: string, userName = 'you') => {
  const context = assistantKnowledge[pathname] ?? assistantKnowledge.default;
  const lower = question.toLowerCase();

  let answer = `${context.intro}\n\nRecommended next move: ${context.nextAction}`;

  if (lower.includes('graph') || lower.includes('chart') || lower.includes('map')) {
    answer = `Here is how to read the ${context.title.toLowerCase()} visuals for ${userName}.\n\n${context.sources
      .map((source) => `${source.title}: ${source.detail}`)
      .join(' ')}`;
  } else if (
    lower.includes('next') ||
    lower.includes('do now') ||
    lower.includes('priority') ||
    lower.includes('what should')
  ) {
    answer = `Top priority for ${userName}: ${context.nextAction}\n\nWhy this matters: ${context.intro}`;
  } else if (lower.includes('folio') || lower.includes('portfolio')) {
    answer = `Folio angle for ${userName}: ${context.sources
      .filter((source) => source.tag === 'Folio' || source.tag === 'Narrative' || source.tag === 'Lift')
      .map((source) => source.detail)
      .join(' ') || context.nextAction}`;
  } else if (lower.includes('summary') || lower.includes('summarize')) {
    answer = `Summary for ${context.title}: ${context.intro}\n\nKeep an eye on: ${context.sources
      .slice(0, 2)
      .map((source) => source.detail)
      .join(' ')}`;
  }

  return {
    answer,
    confidence: 0.87,
    sources: context.sources,
    title: context.title,
    prompts: context.prompts,
  };
};
