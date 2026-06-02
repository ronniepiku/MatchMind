import { Routes, Route } from "react-router-dom";
import { Layout } from "@/components/layout";
import {
  Dashboard,
  OpponentProfile,
  PlayerPerformance,
  TeamScorecard,
  MatchAnalysis,
  PlayerComparison,
  Simulation,
} from "@/pages";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="opponent" element={<OpponentProfile />} />
        <Route path="player" element={<PlayerPerformance />} />
        <Route path="scorecard" element={<TeamScorecard />} />
        <Route path="match" element={<MatchAnalysis />} />
        <Route path="comparison" element={<PlayerComparison />} />
        <Route path="simulation" element={<Simulation />} />
      </Route>
    </Routes>
  );
}