import { Navigate, Route, Routes } from "react-router-dom";
import { useAuthStore } from "./store/authStore";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Agent } from "./pages/Agent";
import { Devices } from "./pages/Devices";
import { Settings } from "./pages/Settings";
import { Audit } from "./pages/Audit";
import { Organisation } from "./pages/Organisation";
import { DirectMode } from "./pages/DirectMode";
import { Inspector } from "./pages/Inspector";
import { MSSPDashboard } from "./pages/MSSPDashboard";
import { AcceptInvite } from "./pages/AcceptInvite";
import { Servers } from "./pages/Servers";
import { ServerDirectMode } from "./pages/ServerDirectMode";
import { ServerAnalysis } from "./pages/ServerAnalysis";
import { Remediation } from "./pages/Remediation";
import { Compliance } from "./pages/Compliance";
import { Sidebar } from "./components/layout/Sidebar";
import { SupportBanner } from "./components/layout/SupportBanner";

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return (
    <div className="flex">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <SupportBanner />
        {children}
      </div>
    </div>
  );
}

export function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/invite/:token" element={<AcceptInvite />} />
      <Route path="/" element={<ProtectedLayout><Dashboard /></ProtectedLayout>} />
      <Route path="/agent" element={<ProtectedLayout><Agent /></ProtectedLayout>} />
      <Route path="/devices" element={<ProtectedLayout><Devices /></ProtectedLayout>} />
      {/* Redirects for consolidated Dispositivos tabs */}
      <Route path="/templates" element={<Navigate to="/devices" replace />} />
      <Route path="/device-groups" element={<Navigate to="/devices" replace />} />
      <Route path="/variables" element={<Navigate to="/devices" replace />} />
      {/* Redirects for consolidated Auditoria tabs */}
      <Route path="/bulk-jobs" element={<Navigate to="/audit" replace />} />
      <Route path="/bulk-jobs/:id" element={<Navigate to="/audit" replace />} />
      <Route path="/operations" element={<Navigate to="/audit" replace />} />
      <Route path="/logs" element={<Navigate to="/audit" replace />} />
      <Route path="/audit" element={<ProtectedLayout><Audit /></ProtectedLayout>} />
      <Route path="/settings" element={<ProtectedLayout><Settings /></ProtectedLayout>} />
      <Route path="/direct-mode" element={<ProtectedLayout><DirectMode /></ProtectedLayout>} />
      <Route path="/inspector" element={<ProtectedLayout><Inspector /></ProtectedLayout>} />
      <Route path="/tenants" element={<Navigate to="/organization" replace />} />
      <Route path="/organization" element={<ProtectedLayout><Organisation /></ProtectedLayout>} />
      <Route path="/mssp" element={<ProtectedLayout><MSSPDashboard /></ProtectedLayout>} />
      <Route path="/servers" element={<ProtectedLayout><Servers /></ProtectedLayout>} />
      <Route path="/server-direct" element={<ProtectedLayout><ServerDirectMode /></ProtectedLayout>} />
      <Route path="/server-analysis" element={<ProtectedLayout><ServerAnalysis /></ProtectedLayout>} />
      <Route path="/remediation" element={<ProtectedLayout><Remediation /></ProtectedLayout>} />
      <Route path="/compliance" element={<ProtectedLayout><Compliance /></ProtectedLayout>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
