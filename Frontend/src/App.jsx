import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { isAuthenticated } from "./api.js";
import Landing from "./pages/Landing.jsx";
import Login from "./pages/Login.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Docs from "./pages/Docs.jsx";
import ForgotPassword from "./pages/ForgotPassword.jsx";
import ResetPassword from "./pages/ResetPassword.jsx";

function Home() {
  // Reading the location re-renders this after the landing page signs a demo in.
  useLocation();
  return isAuthenticated() ? <Dashboard /> : <Landing />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="/docs" element={<Docs />} />
      <Route path="/" element={<Home />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
