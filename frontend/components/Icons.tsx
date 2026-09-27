// SF Symbols-like line icons (24px grid, currentColor).
type P = { size?: number; className?: string; style?: React.CSSProperties };

function Svg({ size = 20, className, style, children }: P & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export const IconChevronLeft = (p: P) => (
  <Svg {...p}><path d="M15 5l-7 7 7 7" /></Svg>
);
export const IconChevronRight = (p: P) => (
  <Svg {...p}><path d="M9 5l7 7-7 7" /></Svg>
);
export const IconArrowUpRight = (p: P) => (
  <Svg {...p}><path d="M7 17L17 7M8 7h9v9" /></Svg>
);
export const IconPlus = (p: P) => (
  <Svg {...p}><path d="M12 5v14M5 12h14" /></Svg>
);
export const IconSearch = (p: P) => (
  <Svg {...p}><circle cx="11" cy="11" r="6.5" /><path d="M20 20l-4.2-4.2" /></Svg>
);
export const IconClose = (p: P) => (
  <Svg {...p}><path d="M6 6l12 12M18 6L6 18" /></Svg>
);
export const IconBuilding = (p: P) => (
  <Svg {...p}>
    <path d="M4 21V5.5A1.5 1.5 0 0 1 5.5 4h8A1.5 1.5 0 0 1 15 5.5V21" />
    <path d="M15 10h3.5A1.5 1.5 0 0 1 20 11.5V21M3 21h18" />
    <path d="M8 8h3M8 12h3M8 16h3" />
  </Svg>
);
export const IconWarning = (p: P) => (
  <Svg {...p}>
    <path d="M10.3 4.3L2.9 17.2A2 2 0 0 0 4.6 20h14.8a2 2 0 0 0 1.7-2.8L13.7 4.3a2 2 0 0 0-3.4 0z" />
    <path d="M12 9.5v4M12 17h.01" />
  </Svg>
);
export const IconEye = (p: P) => (
  <Svg {...p}>
    <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
    <circle cx="12" cy="12" r="3" />
  </Svg>
);
export const IconCamera = (p: P) => (
  <Svg {...p}>
    <path d="M4 8h3l1.6-2.4A1.5 1.5 0 0 1 9.9 5h4.2a1.5 1.5 0 0 1 1.3.6L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z" />
    <circle cx="12" cy="13" r="3.5" />
  </Svg>
);
export const IconCalendar = (p: P) => (
  <Svg {...p}>
    <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" />
    <path d="M3.5 10h17M8 3v4M16 3v4" />
  </Svg>
);
export const IconPin = (p: P) => (
  <Svg {...p}>
    <path d="M12 21s-6.5-6.2-6.5-11A6.5 6.5 0 0 1 12 3.5 6.5 6.5 0 0 1 18.5 10c0 4.8-6.5 11-6.5 11z" />
    <circle cx="12" cy="10" r="2.3" />
  </Svg>
);
export const IconTruck = (p: P) => (
  <Svg {...p}>
    <path d="M2.5 6.5h11v10h-11zM13.5 10h4l3 3.5v3h-7" />
    <circle cx="6.5" cy="17.5" r="1.8" /><circle cx="17" cy="17.5" r="1.8" />
  </Svg>
);
export const IconCheck = (p: P) => (
  <Svg {...p}><path d="M5 12.5l4.5 4.5L19 7.5" /></Svg>
);
export const IconUpload = (p: P) => (
  <Svg {...p}><path d="M12 16V4M7 9l5-5 5 5M4 16v3a1.5 1.5 0 0 0 1.5 1.5h13A1.5 1.5 0 0 0 20 19v-3" /></Svg>
);
export const IconQuestion = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M9.5 9.5a2.5 2.5 0 1 1 3.6 2.2c-.7.4-1.1.9-1.1 1.8M12 16.8h.01" />
  </Svg>
);
export const IconBan = (p: P) => (
  <Svg {...p}><circle cx="12" cy="12" r="9" /><path d="M5.6 5.6l12.8 12.8" /></Svg>
);
export const IconPalette = (p: P) => (
  <Svg {...p}>
    <path d="M12 3.5a8.5 8.5 0 1 0 0 17c1.4 0 2.2-.8 2.2-1.9 0-1-.7-1.5-.7-2.4 0-.9.7-1.7 1.9-1.7h1.9c2 0 3.2-1.5 3.2-3.5C20.5 6.6 16.7 3.5 12 3.5z" />
    <circle cx="7.6" cy="11.5" r="1" /><circle cx="10" cy="7.6" r="1" />
    <circle cx="14.7" cy="7.4" r="1" /><circle cx="17.4" cy="11.3" r="1" />
  </Svg>
);
export const IconSliders = (p: P) => (
  <Svg {...p}><path d="M4 7h10M18 7h2M4 17h4M12 17h8" /><circle cx="16" cy="7" r="2" /><circle cx="10" cy="17" r="2" /></Svg>
);
