import { Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "@/components/layout";
import { ErrorBoundary } from "@/components/shared";
import {
  Dashboard,
  OpponentProfile,
  PlayerPerformance,
  TeamScorecard,
  MatchAnalysis,
  PlayerComparison,
  SimulationsPage,
  MatchdayCalendar,
  AnalysisWorkbench,
} from "@/pages";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
        <Route path="opponent" element={<ErrorBoundary><OpponentProfile /></ErrorBoundary>} />
        <Route path="player" element={<ErrorBoundary><PlayerPerformance /></ErrorBoundary>} />
        <Route path="scorecard" element={<ErrorBoundary><TeamScorecard /></ErrorBoundary>} />
        <Route path="match" element={<ErrorBoundary><MatchAnalysis /></ErrorBoundary>} />
        <Route path="comparison" element={<ErrorBoundary><PlayerComparison /></ErrorBoundary>} />
        <Route path="predictions" element={<ErrorBoundary><SimulationsPage /></ErrorBoundary>} />
        <Route path="simulation" element={<Navigate to="/predictions" replace />} />
        <Route path="matchday" element={<ErrorBoundary><MatchdayCalendar /></ErrorBoundary>} />
        <Route path="analysis" element={<ErrorBoundary><AnalysisWorkbench /></ErrorBoundary>} />
      </Route>
    </Routes>
  );
}