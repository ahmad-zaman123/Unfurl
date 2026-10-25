import { useEffect, useRef, useState } from "react";

import ChangePasswordDialog from "./ChangePasswordDialog.jsx";

/* A fixed set of muted hues; the account id picks one, so a person keeps their colour. */
const AVATAR_COLORS = ["#8a5a44", "#5b6b7c", "#7a4e6d", "#4f6f52", "#9b5d2f", "#3f6b78", "#6d5f8e", "#7c6b3d"];

function hashOf(text) {
  let h = 0;
  for (const ch of String(text)) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h;
}

export function initials(name) {
  const parts = String(name || "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** What to call the person: their name, or the part of the email before the @. */
export function displayName(user) {
  const name = (user?.full_name || "").trim();
  if (name) return name;
  return (user?.email || "").split("@")[0] || "You";
}

export function Avatar({ user, size = "sm" }) {
  const name = displayName(user);
  return (
    <span className={"avatar " + size} style={{ background: AVATAR_COLORS[hashOf(user?.id ?? user?.email ?? "") % AVATAR_COLORS.length] }} aria-hidden="true">
      {initials(name)}
    </span>
  );
}

function Icon({ d }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}
const ICON = {
  sun: "M12 4V2m0 20v-2m8-8h2M2 12h2m13.7-5.7l1.4-1.4M4.9 19.1l1.4-1.4m0-11.4L4.9 4.9m14.2 14.2l-1.4-1.4M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
  moon: "M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z",
  key: "M21 2l-2 2m-7.6 7.6a5.5 5.5 0 1 1-7.8 7.8 5.5 5.5 0 0 1 7.8-7.8zm0 0L19 3m-3.5 3.5L18 9",
  out: "M10 17l5-5-5-5m5 5H3m9-9h7a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1h-7",
};

/**
 * Avatar + first name in the header; opens a menu with the account, Change password and Sign out.
 * `changePassword(payload)` posts to the API; `onPasswordChanged` lets the parent refresh the user.
 */
export default function ProfileMenu({ user, onSignOut, changePassword, onPasswordChanged, children }) {
  const [open, setOpen] = useState(false);
  const [dialog, setDialog] = useState(false);
  const [mode, setMode] = useState("light");
  const ref = useRef(null);
  const firstItem = useRef(null);

  // index.html sets data-theme before first paint; read it once so the switch matches the page.
  useEffect(() => {
    setMode(document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light");
  }, []);

  function setTheme(next) {
    setMode(next);
    try {
      localStorage.setItem("theme", next);
    } catch {
      /* private mode: the choice just will not persist */
    }
    document.documentElement.setAttribute("data-theme", next);
  }

  useEffect(() => {
    if (!open) return undefined;
    firstItem.current?.focus();
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => {
      if (e.key === "Escape") setOpen(false);
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        const items = Array.from(ref.current?.querySelectorAll('[role="menuitem"]') ?? []);
        const i = items.indexOf(document.activeElement);
        const next = e.key === "ArrowDown" ? (i + 1) % items.length : (i - 1 + items.length) % items.length;
        items[next]?.focus();
        e.preventDefault();
      }
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!user) return null;
  const name = displayName(user);

  return (
    <div className="pmenu" ref={ref}>
      <button type="button" className="ptrigger" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open} aria-label="Account menu">
        <Avatar user={user} />
        <span className="pname">{name.split(" ")[0]}</span>
        <svg className="caret" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>
      {open ? (
        <div className="pdrop" role="menu" aria-label="Account">
          <div className="pcardhead">
            <Avatar user={user} size="lg" />
            <div className="pwho">
              <div className="name">{name}</div>
              <div className="hint" title={user.email}>
                {user.email}
              </div>
            </div>
          </div>
          <div className="psep" />
          {children}
          <button
            type="button"
            role="menuitem"
            className="pitem"
            ref={firstItem}
            onClick={() => {
              setOpen(false);
              setDialog(true);
            }}
          >
            <Icon d={ICON.key} />
            {user.has_password === false ? "Set a password" : "Change password"}
          </button>
          <div className="pitem static">
            <Icon d={mode === "dark" ? ICON.moon : ICON.sun} />
            <span>Dark mode</span>
            <button
              type="button"
              role="switch"
              aria-checked={mode === "dark"}
              className={"switch" + (mode === "dark" ? " on" : "")}
              onClick={() => setTheme(mode === "dark" ? "light" : "dark")}
              aria-label="Toggle dark mode"
            >
              <i />
            </button>
          </div>
          <div className="psep" />
          <button type="button" role="menuitem" className="pitem danger" onClick={onSignOut}>
            <Icon d={ICON.out} />
            Sign out
          </button>
        </div>
      ) : null}
      {dialog ? (
        <ChangePasswordDialog
          hasPassword={user.has_password !== false}
          changePassword={changePassword}
          onClose={() => setDialog(false)}
          onChanged={onPasswordChanged}
        />
      ) : null}
    </div>
  );
}
