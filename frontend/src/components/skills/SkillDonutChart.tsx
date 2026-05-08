"use client";

interface SkillDonutItem {
  id: string;
  label: string;
  value: number;
  color: string;
}

interface SkillDonutChartProps {
  items: SkillDonutItem[];
  selectedId?: string | null;
  onSelect?: (item: SkillDonutItem) => void;
  centerLabel?: string;
  centerValue?: string;
}

const radius = 52;
const circumference = 2 * Math.PI * radius;

export function SkillDonutChart({
  items,
  selectedId,
  onSelect,
  centerLabel = "Skills",
  centerValue = "0",
}: SkillDonutChartProps) {
  const total = items.reduce((sum, item) => sum + Math.max(item.value, 0), 0) || 1;
  const segments = items.reduce<
    Array<SkillDonutItem & { dash: number; circleOffset: number; segmentOffset: number }>
  >((accumulator, item) => {
    const consumed = accumulator.reduce((sum, segment) => sum + segment.dash, 0);
    const ratio = Math.max(item.value, 0) / total;
    const dash = ratio * circumference;

    return [
      ...accumulator,
      {
        ...item,
        dash,
        circleOffset: circumference - dash,
        segmentOffset: -consumed,
      },
    ];
  }, []);

  return (
    <div className="relative flex h-[220px] w-[220px] items-center justify-center">
      <svg viewBox="0 0 160 160" className="h-full w-full -rotate-90">
        <circle cx="80" cy="80" r={radius} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="20" />
        {segments.map((item) => {
          return (
            <circle
              key={item.id}
              cx="80"
              cy="80"
              r={radius}
              fill="none"
              stroke={item.color}
              strokeWidth={selectedId === item.id ? 24 : 20}
              strokeLinecap="round"
              strokeDasharray={item.dash >= circumference - 0.1 ? "none" : `${item.dash} ${item.circleOffset}`}
              strokeDashoffset={item.segmentOffset}
              className="cursor-pointer transition-all duration-200"
              onClick={() => onSelect?.(item)}
            />
          );
        })}
      </svg>

      <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
        <p className="text-[10px] font-black uppercase tracking-[0.18em] text-on-surface-variant">
          {centerLabel}
        </p>
        <p className="mt-1 text-3xl font-extrabold tracking-tight text-on-surface">{centerValue}</p>
      </div>
    </div>
  );
}
