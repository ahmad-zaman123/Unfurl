import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, logout } from "../api.js";
import ApiKeys from "../components/ApiKeys.jsx";
import Brand from "../components/Brand.jsx";
import Playground from "../components/Playground.jsx";
import ProfileMenu from "../components/ProfileMenu.jsx";
import ThemeToggle from "../components/ThemeToggle.jsx";
import Usage from "../components/Usage.jsx";
import { useDocumentTitle } from "../utils/useDocumentTitle.js";

export default function Dashboard() {
  useDocumentTitle("Dashboard");
  const navigate = useNavigate();
  const [user, setUser] = useState(null);

  const loadUser = useCallback(
    () =>
      api
        .me()
        .then(setUser)
        .catch(() => {
          logout();
          navigate("/login");
        }),
    [navigate],
  );

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  function handleLogout() {
    logout();
    navigate("/login");
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <Brand />
        <div className="topbar-right">
          <button className="btn ghost small" onClick={() => navigate("/docs")}>
            Docs
          </button>
          <ProfileMenu user={user} onSignOut={handleLogout} changePassword={api.changePassword} onPasswordChanged={loadUser} />
          <ThemeToggle />
        </div>
      </header>

      <main className="dashboard">
        <h1 className="sr-only">Dashboard</h1>
        <Playground />
        <div className="dashboard-split">
          <Usage />
          <ApiKeys />
        </div>
      </main>
    </div>
  );
}
