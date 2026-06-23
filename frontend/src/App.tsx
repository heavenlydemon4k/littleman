import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { Sidebar } from "./components/sidebar/Sidebar";
import { ChatPage } from "./pages/ChatPage";
import { SettingsPage } from "./pages/SettingsPage";
import { WorkspacePage } from "./pages/WorkspacePage";
import { AgentPage } from "./pages/AgentPage";
import { OnboardingPage } from "./pages/OnboardingPage";

export default function App() {
  // First-run gate: onboarding is compulsory before the main app.
  const [onboarded, setOnboarded] = useState<boolean | null>(null);

  useEffect(() => {
    fetch("/api/onboarding/status")
      .then((r) => r.json())
      .then((s) => setOnboarded(Boolean(s.onboarded)))
      .catch(() => setOnboarded(true)); // fail open: don't trap the user if the check errors
  }, []);

  if (onboarded === null) {
    return (
      <div className="flex h-screen items-center justify-center bg-surface-0 text-muted">
        <Loader2 className="animate-spin" />
      </div>
    );
  }

  if (!onboarded) {
    return <OnboardingPage onDone={() => setOnboarded(true)} />;
  }

  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden bg-surface-0 text-white">
        <Sidebar />
        <main className="flex flex-1 flex-col overflow-hidden">
          <Routes>
            <Route path="/" element={<Navigate to="/agent" replace />} />
            <Route path="/agent" element={<AgentPage />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/chat/:sessionId" element={<ChatPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/workspace" element={<WorkspacePage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
