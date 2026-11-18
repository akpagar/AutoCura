import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { Sidebar } from "./components/Sidebar";
import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { MonitoringPage } from "./pages/MonitoringPage";
import { PredictionPage } from "./pages/PredictionPage";
import { RecoveryPage } from "./pages/RecoveryPage";
import { SimulationPage } from "./pages/SimulationPage";
import { AlertsPage } from "./pages/AlertsPage";
import { LogsPage } from "./pages/LogsPage";

function RequireAuth({ children }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function AppShell({ children }) {
  return (
    <div className="app-shell">
      <Sidebar />
      <div className="main">{children}</div>
    </div>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<RequireAuth><AppShell><DashboardPage /></AppShell></RequireAuth>} />
      <Route path="/monitoring" element={<RequireAuth><AppShell><MonitoringPage /></AppShell></RequireAuth>} />
      <Route path="/predictions" element={<RequireAuth><AppShell><PredictionPage /></AppShell></RequireAuth>} />
      <Route path="/simulation" element={<RequireAuth><AppShell><SimulationPage /></AppShell></RequireAuth>} />
      <Route path="/recovery" element={<RequireAuth><AppShell><RecoveryPage /></AppShell></RequireAuth>} />
      <Route path="/alerts" element={<RequireAuth><AppShell><AlertsPage /></AppShell></RequireAuth>} />
      <Route path="/logs" element={<RequireAuth><AppShell><LogsPage /></AppShell></RequireAuth>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
