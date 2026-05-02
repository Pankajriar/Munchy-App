import { useCallback, useEffect, useMemo, useState } from "react";
import { Camera, Flame, Gauge, History, Sparkles } from "lucide-react";
import { ScannerWorkspace } from "@/components/ScannerWorkspace";
import { getScanHistory, getUserStreak } from "@/lib/api";

export default function ScannerPage({ user }) {
  const [history, setHistory] = useState([]);
  const [streak, setStreak] = useState({ streak_count: 0, last_scan_date: null });

  const loadHistory = useCallback(async () => {
    try {
      const payload = await getScanHistory();
      setHistory(payload);
    } catch {
      setHistory([]);
    }
  }, []);

  const loadStreak = useCallback(async () => {
    try {
      const data = await getUserStreak();
      setStreak(data);
    } catch {
      setStreak({ streak_count: 0, last_scan_date: null });
    }
  }, []);

  useEffect(() => {
    loadHistory();
    loadStreak();
  }, [loadHistory, loadStreak]);

  const handleScanSaved = useCallback(async () => {
    await loadHistory();
    await loadStreak();
  }, [loadHistory, loadStreak]);

  const summary = useMemo(() => {
    const totalScans = history.length;
    const totalCalories = history.reduce((sum, item) => sum + (item.result?.totalCalories || 0), 0);
    const averageCalories = totalScans ? Math.round(totalCalories / totalScans) : 0;
    return {
      totalScans,
      averageCalories,
      latestMeal: history[0]?.result?.foodName || "Your first scan will appear here",
    };
  }, [history]);

  const streakDisplay = streak.streak_count > 0
    ? `${streak.streak_count} Day Streak \uD83D\uDD25`
    : "No streak yet";

  return (
    <div className="page-enter space-y-6" data-testid="scanner-page">
      <section className="grid items-start gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="glass-panel rounded-[34px] p-6 sm:p-8">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#FF8C00] to-[#FFB347] text-white">
              <Camera className="h-5 w-5" />
            </div>
            <p className="badge-label" data-testid="scanner-page-kicker">AI Photo Scan Dashboard</p>
          </div>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight text-[var(--app-text)] sm:text-5xl" data-testid="scanner-page-title">Hey {user.name.split(" ")[0]}, ready to scan? {"\uD83D\uDCF8"}</h1>
          <p className="mt-4 max-w-2xl text-base text-[var(--app-text-soft)] md:text-lg" data-testid="scanner-page-description">
            Snap a photo of your meal and let Munchy's AI break down the calories, macros, and ingredients for you.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-1">
          <div className="glass-panel rounded-[30px] p-5" data-testid="streak-card">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-[rgba(255,140,0,0.2)] to-[rgba(255,140,0,0.08)] text-[var(--app-primary)]">
              <Flame className="h-5 w-5" />
            </div>
            <p className="mt-4 badge-label">Streak</p>
            <p className="mt-3 text-lg font-semibold text-[var(--app-text)]" data-testid="scanner-summary-streak">{streakDisplay}</p>
          </div>
          {[
            ["Total scans", summary.totalScans, Gauge, "scanner-summary-total-scans"],
            ["Average calories", `${summary.averageCalories} kcal`, Sparkles, "scanner-summary-average-calories"],
            ["Latest meal", summary.latestMeal, History, "scanner-summary-latest-meal"],
          ].map(([label, value, Icon, testId]) => (
            <div className="glass-panel rounded-[30px] p-5" key={label}>
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-[rgba(50,205,50,0.2)] to-[rgba(50,205,50,0.08)] text-[var(--app-secondary)]">
                <Icon className="h-5 w-5" />
              </div>
              <p className="mt-4 badge-label">{label}</p>
              <p className="mt-3 text-lg font-semibold text-[var(--app-text)]" data-testid={testId}>{value}</p>
            </div>
          ))}
        </div>
      </section>

      <ScannerWorkspace onScanSaved={handleScanSaved} recentScans={history.slice(0, 3)} user={user} />
    </div>
  );
}
