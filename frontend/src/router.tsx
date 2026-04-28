import { Navigate, Route, Routes } from "react-router-dom";
import { useAuthStore } from "./store/authStore";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Agent } from "./pages/Agent";
import { Devices } from "./pages/Devices";
import { Operations } from "./pages/Operations";
import { Logs } from "./pages/Logs";
import { Settings } from "./pages/Settings";
import { Audit } from "./pages/Audit";
import { DirectMode } from "./pages/DirectMode";
import { Templates } from "./pages/Templates";
import { Inspector } from "./pages/Inspector";
import { Tenants } from "./pages/Tenants";
import { MSSPDashboard } from "./pages/MSSPDashboard";
import { AcceptInvite } from "./pages/AcceptInvite";
import { BulkJobs } from "./pages/BulkJobs";
import { DeviceGroups } from "./pages/DeviceGroups";
import { Variables } from "./pages/Variables";
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
      <Route
        path="/"
        element={
          <ProtectedLayout>
            <Dashboard />
          </ProtectedLayout>
        }
      />
      <Route
        path="/agent"
        element={
          <ProtectedLayout>
            <Agent />
          </ProtectedLayout>
        }
      />
      <Route
        path="/devices"
        element={
          <ProtectedLayout>
            <Devices />
          </ProtectedLayout>
        }
      />
      <Route
        path="/operations"
        element={
          <ProtectedLayout>
            <Operations />
          </ProtectedLayout>
        }
      />
      <Route
        path="/audit"
        element={
          <ProtectedLayout>
            <Audit />
          </ProtectedLayout>
        }
      />
      <Route
        path="/logs"
        element={
          <ProtectedLayout>
            <Logs />
          </ProtectedLayout>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedLayout>
            <Settings />
          </ProtectedLayout>
        }
      />
      <Route
        path="/direct-mode"
        element={
          <ProtectedLayout>
            <DirectMode />
          </ProtectedLayout>
        }
      />
      <Route
        path="/templates"
        element={
          <ProtectedLayout>
            <Templates />
          </ProtectedLayout>
        }
      />
      <Route
        path="/inspector"
        element={
          <ProtectedLayout>
            <Inspector />
          </ProtectedLayout>
        }
      />
      <Route
        path="/tenants"
        element={
          <ProtectedLayout>
            <Tenants />
          </ProtectedLayout>
        }
      />
      <Route
        path="/mssp"
        element={
          <ProtectedLayout>
            <MSSPDashboard />
          </ProtectedLayout>
        }
      />
      <Route
        path="/device-groups"
        element={
          <ProtectedLayout>
            <DeviceGroups />
          </ProtectedLayout>
        }
      />
      <Route
        path="/bulk-jobs"
        element={
          <ProtectedLayout>
            <BulkJobs />
          </ProtectedLayout>
        }
      />
      <Route
        path="/bulk-jobs/:id"
        element={
          <ProtectedLayout>
            <BulkJobs />
          </ProtectedLayout>
        }
      />
      <Route
        path="/variables"
        element={
          <ProtectedLayout>
            <Variables />
          </ProtectedLayout>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
