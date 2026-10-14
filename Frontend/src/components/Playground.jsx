import { useEffect, useMemo, useState } from "react";

import { api } from "../api.js";
import { API_BASE, shellQuote } from "../lib.js";
import CodeBlock from "./CodeBlock.jsx";
import Proof from "./Proof.jsx";

const TEMPLATES = [
  { value: "generic", label: "Generic" },
  { value: "article", label: "Article" },
  { value: "product", label: "Product" },
  { value: "event", label: "Event" },
];

const THEMES = [
  { value: "brand", label: "Brand" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const INITIAL = {
  template: "generic",
  theme: "brand",
  accent: "#2563eb",
  title: "Ship link previews that don't look broken",
  subtitle: "Generate og:images for any link with one API call.",
  eyebrow: "unfurl.app",
  footer: "Ada Lovelace · Engineering",
  logo: "",
  price: "$149",
  date: "Sat, Aug 16 · 6:00 PM",
  location: "San Francisco, CA",
};

export default function Playground() {
  const [spec, setSpec] = useState(INITIAL);
  const [url, setUrl] = useState("");
  const [phase, setPhase] = useState("rendering"); // rendering | ready | error
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  function update(key, value) {
    setSpec((prev) => ({ ...prev, [key]: value }));
  }

  // Only send the fields the chosen template actually renders.
  const params = useMemo(() => {
    const base = {
      template: spec.template,
      theme: spec.theme,
      accent: spec.accent,
      title: spec.title,
      subtitle: spec.subtitle,
      eyebrow: spec.eyebrow,
      footer: spec.footer,
      logo: spec.logo,
    };
    if (spec.template === "product") base.price = spec.price;
    if (spec.template === "event") {
      base.date = spec.date;
      base.location = spec.location;
    }
    return base;
  }, [spec]);

  // The request exactly as a developer would send it, without the empty fields.
  const curl = useMemo(() => {
    const body = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== ""));
    return (
      "curl -X POST " + API_BASE + "/api/v1/cards \\\n" +
      '  -H "Authorization: Bearer sk_live_YOUR_KEY" \\\n' +
      '  -H "Content-Type: application/json" \\\n' +
      "  -d " + shellQuote(JSON.stringify(body, null, 2))
    );
  }, [params]);

  // Debounced call to the authenticated create endpoint, which returns a signed public URL.
  useEffect(() => {
    if (!params.title) return undefined;
    setPhase("rendering");
    const handle = setTimeout(() => {
      api
        .createCard(params)
        .then((response) => {
          setError("");
          setUrl(response.url);
        })
        .catch((err) => {
          setPhase("error");
          setError(err?.message || "The card could not be rendered.");
        });
    }, 350);
    return () => clearTimeout(handle);
  }, [params]);

  async function copyUrl() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }

  const stale = phase === "rendering" || phase === "error";

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>Proof</h2>
        <span className="muted">Every change re-renders through the signed API</span>
      </div>

      <div className="playground">
        <div className="pg-form">
          <div className="pg-row">
            <label className="field">
              <span>Template</span>
              <select value={spec.template} onChange={(e) => update("template", e.target.value)}>
                {TEMPLATES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Theme</span>
              <select value={spec.theme} onChange={(e) => update("theme", e.target.value)}>
                {THEMES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="field">
            <span>Accent</span>
            <div className="color-row">
              <input type="color" value={spec.accent} onChange={(e) => update("accent", e.target.value)} />
              <code>{spec.accent}</code>
            </div>
          </label>

          <label className="field">
            <span>Eyebrow</span>
            <input value={spec.eyebrow} onChange={(e) => update("eyebrow", e.target.value)} maxLength={120} />
          </label>

          <label className="field">
            <span>Title (required)</span>
            <textarea rows={2} value={spec.title} onChange={(e) => update("title", e.target.value)} maxLength={200} />
          </label>

          <label className="field">
            <span>Subtitle</span>
            <input value={spec.subtitle} onChange={(e) => update("subtitle", e.target.value)} maxLength={200} />
          </label>

          {spec.template === "product" && (
            <label className="field">
              <span>Price</span>
              <input value={spec.price} onChange={(e) => update("price", e.target.value)} maxLength={120} />
            </label>
          )}

          {spec.template === "event" && (
            <div className="pg-row">
              <label className="field">
                <span>Date</span>
                <input value={spec.date} onChange={(e) => update("date", e.target.value)} maxLength={120} />
              </label>
              <label className="field">
                <span>Location</span>
                <input value={spec.location} onChange={(e) => update("location", e.target.value)} maxLength={120} />
              </label>
            </div>
          )}

          <label className="field">
            <span>Footer</span>
            <input value={spec.footer} onChange={(e) => update("footer", e.target.value)} maxLength={120} />
          </label>

          <label className="field">
            <span>Logo URL (optional)</span>
            <input
              value={spec.logo}
              onChange={(e) => update("logo", e.target.value)}
              placeholder="https://example.com/logo.png"
            />
          </label>
        </div>

        <div className="pg-preview">
          <Proof caption={<span>1200 × 630 · og:image</span>}>
            <div className={"proof-sheet" + (stale ? " is-stale" : "")}>
              {url ? (
                <img
                  src={url}
                  alt="Live preview of the generated card"
                  onLoad={() => setPhase("ready")}
                  onError={() => {
                    setPhase("error");
                    setError("The image URL did not load. Try again in a moment.");
                  }}
                />
              ) : (
                <div className="proof-empty">{params.title ? "Rendering the first proof…" : "Add a title to render a card."}</div>
              )}
              {phase === "rendering" && url && <span className="proof-status" role="status">Rendering…</span>}
            </div>
          </Proof>

          {phase === "error" && (
            <div className="error-banner" role="alert">
              {error}
            </div>
          )}

          <div className="url-bar">
            <code title={url}>{url || "The signed URL appears here"}</code>
            <button className="btn primary small" onClick={copyUrl} disabled={!url}>
              {copied ? "Copied" : "Copy URL"}
            </button>
          </div>

          <CodeBlock label="The request behind this card">{curl}</CodeBlock>
        </div>
      </div>
    </div>
  );
}
