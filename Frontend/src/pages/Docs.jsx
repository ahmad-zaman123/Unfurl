import { Link } from "react-router-dom";

const API = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8010").replace(/\/+$/, "");

const PARAMS = [
  ["template", "generic · article · product · event"],
  ["theme", "brand · light · dark"],
  ["accent", "hex colour, e.g. #2563eb"],
  ["title", "headline (required)"],
  ["subtitle", "supporting line"],
  ["eyebrow", "small label above the title (site / brand / category)"],
  ["footer", "author, date, or any small line"],
  ["price", "product template only"],
  ["date, location", "event template only"],
  ["logo", "http(s) image URL, composited top-right (SSRF-guarded)"],
];

function Code({ children }) {
  return <pre className="docs-code">{children}</pre>;
}

export default function Docs() {
  return (
    <div className="docs">
      <header className="landing-nav">
        <Link to="/" className="landing-logo docs-home">
          <span className="brand">Unfurl</span>
        </Link>
        <Link to="/login" className="link-btn">
          Sign in
        </Link>
      </header>

      <main className="docs-body">
        <h1>Quickstart</h1>
        <p className="muted">
          Unfurl generates <code>og:image</code> social preview cards from a single API
          call. You authenticate to <strong>mint a signed URL</strong>, then drop that
          public URL into a meta tag — crawlers fetch it with no auth needed.
        </p>

        <h2>1. Get an API key</h2>
        <p className="muted">
          Create a key from your <Link to="/login">dashboard</Link>. It looks like{" "}
          <code>sk_live_…</code> and is shown only once.
        </p>

        <h2>2. Create a card</h2>
        <p className="muted">
          POST a spec with your key. The response is a signed, cacheable image URL.
        </p>
        <Code>{`curl -X POST ${API}/api/v1/cards \\
  -H "Authorization: Bearer sk_live_your_key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "template": "article",
    "theme": "brand",
    "title": "How we cut cold-start latency by 80%",
    "eyebrow": "Engineering",
    "footer": "Grace Hopper · Jul 2026"
  }'

# → { "url": "${API}/api/v1/og?...&sig=..." }`}</Code>

        <h2>3. Use it in your HTML</h2>
        <Code>{`<meta property="og:image" content="${API}/api/v1/og?...&sig=..." />`}</Code>
        <p className="muted">
          The image URL is signed, so its parameters can&apos;t be tampered with, and it
          is cached after the first render.
        </p>

        <h2>Parameters</h2>
        <table className="docs-table">
          <tbody>
            {PARAMS.map(([name, desc]) => (
              <tr key={name}>
                <td>
                  <code>{name}</code>
                </td>
                <td className="muted">{desc}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h2>Rate limits</h2>
        <p className="muted">
          Limits apply per key by plan (Free: 60/min, 5,000/day; monthly quota per
          account). Responses include <code>X-RateLimit-*</code> headers and a{" "}
          <code>Retry-After</code> on <code>429</code>.
        </p>

        <h2>Reference</h2>
        <p className="muted">
          Full interactive API reference:{" "}
          <a href={API + "/api/docs/"} target="_blank" rel="noreferrer">
            Swagger UI
          </a>
          .
        </p>
      </main>
    </div>
  );
}
