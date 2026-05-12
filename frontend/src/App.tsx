import { useEffect } from "react";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "react-hot-toast";
import { AppRouter } from "./router";
import { useAuthStore } from "./store/authStore";
import { StagingBanner } from "./components/layout/StagingBanner";
import { AgentDrawer } from "./components/layout/AgentDrawer";
import { AssistantFab } from "./components/assistant/AssistantFab";
import { AssistantPanel } from "./components/assistant/AssistantPanel";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

function AuthInit() {
  const fetchMe = useAuthStore((s) => s.fetchMe);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    if (isAuthenticated) {
      fetchMe();
    }
  }, [isAuthenticated, fetchMe]);

  return null;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <StagingBanner />
        <AuthInit />
        <AppRouter />
        <AgentDrawer />
        <AssistantFab />
        <AssistantPanel />
        <Toaster position="top-right" />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
