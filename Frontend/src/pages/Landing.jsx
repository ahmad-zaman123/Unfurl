import { Link } from "react-router-dom";

function LogoMark() {
  return (
    <span className="logo-mark" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none">
        <rect
          x="4"
          y="6"
          width="16"
          height="13"
          rx="2.5"
          stroke="currentColor"
          strokeWidth="1.7"
        />
        <path
          d="M5 17l4.5-4 3 2.5L17 11l2 2"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        <circle cx="9" cy="11" r="1.4" fill="currentColor" />
      </svg>
    </span>
  );
}

export default function Landing() {
  return (
    <div className="landing">
      <div className="landing-glow" aria-hidden="true" />

      <header className="landing-nav">
        <div className="landing-logo">
          <LogoMark />
          <span className="brand">Unfurl</span>
        </div>
        <nav className="landing-nav-links">
          <Link to="/docs" className="link-btn">
            Docs
          </Link>
          <Link to="/login" className="link-btn">
            Sign in
          </Link>
        </nav>
      </header>

      <main className="landing-hero">
        <div className="hero-copy">
          <span className="landing-eyebrow">Developer API</span>
          <h1 className="landing-title">
            Social cards, <span className="grad">generated</span> by API.
          </h1>
          <p className="landing-lede">
            Call one endpoint and get a ready-to-use <code>og:image</code> for any link —
            dynamic titles, themes, and logos, cached and served CDN-fast.
          </p>
          <div className="landing-cta">
            <Link to="/login" state={{ register: true }} className="btn primary">
              Get started — it&apos;s free
            </Link>
            <Link to="/login" state={{ demo: true }} className="btn outline">
              Try the live demo
            </Link>
          </div>
        </div>

        <div className="hero-preview" aria-hidden="true">
          <div className="preview-card">
            <div className="preview-head">
              <span className="preview-dot" />
              <span className="preview-dot" />
              <span className="preview-dot" />
              <span className="preview-file">og:image · 1200×630</span>
            </div>
            <div className="og-card">
              <div className="og-eyebrow">unfurl.app</div>
              <div className="og-title">Introducing Unfurl</div>
              <div className="og-foot">
                <span className="og-avatar" />
                <span>Ada Lovelace · Engineering</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
