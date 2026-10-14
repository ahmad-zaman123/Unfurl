import { Link } from "react-router-dom";

/** Sign-in and sign-up are reached from the landing page, so give a way back to it. */
export default function BackLink({ to = "/", children = "Back to home" }) {
  return (
    <Link to={to} className="back-link">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
        <path d="M19 12H5M11 6l-6 6 6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      {children}
    </Link>
  );
}
