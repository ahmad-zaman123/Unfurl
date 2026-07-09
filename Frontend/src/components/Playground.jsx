import { useEffect, useMemo, useState } from "react";

import { api } from "../api.js";

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
    if (spec.template === "product") {
      base.price = spec.price;
    }
    if (spec.template === "event") {
      base.date = spec.date;
      base.location = spec.location;
    }
    return base;
  }, [spec]);

  // Debounced call to the authenticated create endpoint, which returns a
  // signed public URL that the <img> below then loads.
  useEffect(() => {
    if (!params.title) {
      return undefined;
    }
    const handle = setTimeout(() => {
      api
        .createCard(params)
        .then((response) => setUrl(response.url))
        .catch(() => {});
    }, 350);
    return () => clearTimeout(handle);
  }, [params]);

  async function copyUrl() {
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
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
            <input
              type="color"
              value={spec.accent}
              onChange={(e) => update("accent", e.target.value)}
            />
            <code>{spec.accent}</code>
          </div>
        </label>

        <label className="field">
          <span>Eyebrow</span>
          <input value={spec.eyebrow} onChange={(e) => update("eyebrow", e.target.value)} />
        </label>

        <label className="field">
          <span>Title</span>
          <textarea rows={2} value={spec.title} onChange={(e) => update("title", e.target.value)} />
        </label>

        <label className="field">
          <span>Subtitle</span>
          <input value={spec.subtitle} onChange={(e) => update("subtitle", e.target.value)} />
        </label>

        {spec.template === "product" && (
          <label className="field">
            <span>Price</span>
            <input value={spec.price} onChange={(e) => update("price", e.target.value)} />
          </label>
        )}

        {spec.template === "event" && (
          <div className="pg-row">
            <label className="field">
              <span>Date</span>
              <input value={spec.date} onChange={(e) => update("date", e.target.value)} />
            </label>
            <label className="field">
              <span>Location</span>
              <input value={spec.location} onChange={(e) => update("location", e.target.value)} />
            </label>
          </div>
        )}

        <label className="field">
          <span>Footer</span>
          <input value={spec.footer} onChange={(e) => update("footer", e.target.value)} />
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
        <div className="preview-card">
          <div className="preview-head">
            <span className="preview-dot" />
            <span className="preview-dot" />
            <span className="preview-dot" />
            <span className="preview-file">og:image · 1200×630</span>
          </div>
          {url && <img src={url} alt="Live card preview" className="pg-image" />}
        </div>
        <div className="url-bar">
          <code title={url}>{url || "…"}</code>
          <button className="btn primary small" onClick={copyUrl} disabled={!url}>
            {copied ? "Copied" : "Copy URL"}
          </button>
        </div>
      </div>
    </div>
  );
}
