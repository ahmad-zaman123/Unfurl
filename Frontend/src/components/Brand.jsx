export function LogoMark({ size = 22 }) {
  return (
    <svg className="logo-mark" viewBox="0 0 24 24" width={size} height={size} fill="none" aria-hidden="true">
      <rect x="6.5" y="7.5" width="11" height="9" stroke="currentColor" strokeWidth="1.6" />
      <path
        d="M3 7.5V3h4.5M16.5 3H21v4.5M21 16.5V21h-4.5M7.5 21H3v-4.5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="square"
      />
    </svg>
  );
}

export default function Brand() {
  return (
    <span className="brand">
      <LogoMark />
      Unfurl
    </span>
  );
}
