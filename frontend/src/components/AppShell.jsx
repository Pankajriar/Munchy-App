import { Camera, HeartPulse, History, LogOut, MessageCircle, Mail, ScanSearch, Share2, Sparkles, Utensils } from "lucide-react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const navClass = ({ isActive }) =>
  cn(
    "link-pill border border-transparent text-[var(--app-text-soft)] hover:-translate-y-0.5 hover:bg-white hover:text-[var(--app-text)]",
    isActive && "border-[rgba(255,140,0,0.15)] bg-white text-[var(--app-text)] shadow-sm",
  );

const handleInviteFriend = () => {
  const shareData = {
    title: "Munchy \u2014 AI Food Scanner",
    text: "Check out Munchy, the AI calorie tracker I use! Snap a photo and instantly get nutrition info.",
    url: window.location.origin,
  };

  if (navigator.share) {
    navigator.share(shareData).catch(() => {});
  } else {
    navigator.clipboard
      .writeText(`${shareData.text} ${shareData.url}`)
      .then(() => alert("Link copied to clipboard!"))
      .catch(() => {});
  }
};

export const AppShell = ({ authLoading, children, onLogout, onOpenAuth, user }) => {
  const location = useLocation();

  return (
    <div className="relative min-h-screen overflow-hidden grain-overlay">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[440px] opacity-90"
        style={{
          backgroundImage:
            "url(https://static.prod-images.emergentagent.com/jobs/a654a202-2f4b-499f-ba99-7a8645ec45c8/images/d444a9833c0116265be88e9fc7054a4aea357e1494d618b3c1ed2bfac3999fd9.png)",
          backgroundPosition: "center top",
          backgroundRepeat: "no-repeat",
          backgroundSize: "cover",
        }}
      />

      <header className="section-shell sticky top-0 z-30 pt-4 sm:pt-6">
        <div className="glass-panel halo-ring flex flex-col gap-5 rounded-[32px] px-5 py-5 sm:px-7 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center justify-between gap-4">
            <Link className="flex items-center gap-3" data-testid="app-logo-link" to="/">
              {/*
                \u2500\u2500 Munchy Logo Placeholder \u2500\u2500
                Replace the <div> below with an <img> tag pointing to your PNG logo asset:
                  <img src=\"/assets/munchy-logo.png\" alt=\"Munchy\" className=\"h-12 w-12 rounded-2xl shadow-[0_18px_40px_rgba(255,140,0,0.28)]\" />
                Keep the surrounding Link and text elements as-is.
              */}
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-[#FF8C00] to-[#FFB347] text-white shadow-[0_18px_40px_rgba(255,140,0,0.28)]" data-testid="app-logo-icon">
                <Utensils className="h-6 w-6" />
              </div>
              <div>
                <p className="badge-label" data-testid="app-logo-kicker">AI Food Scanner</p>
                <h1 className="text-xl font-semibold munchy-gradient-text" data-testid="app-logo-title">Munchy</h1>
              </div>
            </Link>

            <div className="rounded-full border border-[rgba(255,140,0,0.12)] bg-white/80 px-3 py-2 text-xs font-semibold text-[var(--app-text-soft)] lg:hidden" data-testid="mobile-status-pill">
              {user ? "\uD83C\uDF4A Member" : authLoading ? "Loading" : "Guest"}
            </div>
          </div>

          <div className="flex flex-col gap-4 lg:flex-row lg:items-center">
            <nav className="flex flex-wrap gap-2" data-testid="app-main-navigation">
              <NavLink className={navClass} data-testid="nav-home-link" to="/">
                <HeartPulse className="h-4 w-4" />
                Home
              </NavLink>

              {user ? (
                <>
                  <NavLink className={navClass} data-testid="nav-scanner-link" to="/scanner">
                    <Camera className="h-4 w-4" />
                    AI Photo Scan
                  </NavLink>
                  <NavLink className={navClass} data-testid="nav-history-link" to="/history">
                    <History className="h-4 w-4" />
                    History
                  </NavLink>
                </>
              ) : (
                <>
                  <button className={navClass({ isActive: location.pathname === "/scanner" })} data-testid="nav-scanner-auth-button" onClick={onOpenAuth} type="button">
                    <Camera className="h-4 w-4" />
                    AI Photo Scan
                  </button>
                  <button className={navClass({ isActive: location.pathname === "/history" })} data-testid="nav-history-auth-button" onClick={onOpenAuth} type="button">
                    <History className="h-4 w-4" />
                    History
                  </button>
                </>
              )}
            </nav>

            <div className="flex flex-wrap items-center gap-3">
              {user ? (
                <>
                  <div className="flex items-center gap-3 rounded-full border border-[rgba(255,140,0,0.12)] bg-white/90 px-4 py-2" data-testid="authenticated-user-badge">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-[rgba(50,205,50,0.2)] to-[rgba(50,205,50,0.08)] text-sm font-bold text-[var(--app-secondary)]">
                      {user.name?.charAt(0)?.toUpperCase()}
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-[var(--app-text)]" data-testid="authenticated-user-name">{user.name}</p>
                      <p className="text-xs text-[var(--app-text-muted)]" data-testid="authenticated-user-email">{user.email}</p>
                    </div>
                  </div>
                  <Button
                    className="rounded-full border border-[rgba(255,140,0,0.15)] bg-white px-5 text-[var(--app-text)] hover:bg-[var(--app-muted)]"
                    data-testid="invite-friend-button"
                    onClick={handleInviteFriend}
                    type="button"
                    variant="outline"
                  >
                    <Share2 className="mr-1 h-4 w-4" />
                    Invite a Friend
                  </Button>
                  <Button className="rounded-full bg-[var(--app-text)] px-5 text-white hover:bg-[var(--app-text)]/90" data-testid="logout-button" onClick={onLogout} type="button">
                    <LogOut className="mr-1 h-4 w-4" />
                    Sign out
                  </Button>
                </>
              ) : (
                <Button className="rounded-full bg-gradient-to-r from-[#FF8C00] to-[#FFB347] px-5 text-white shadow-[0_18px_40px_rgba(255,140,0,0.25)] hover:from-[#E67E00] hover:to-[#FF8C00]" data-testid="open-auth-dialog-button" onClick={onOpenAuth} type="button">
                  <Sparkles className="mr-1 h-4 w-4" />
                  Join Munchy
                </Button>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="section-shell relative z-10 pb-8 pt-8 sm:pt-10" data-testid="app-shell-content">
        {children}
      </main>

      <footer className="section-shell relative z-10 pb-8" data-testid="app-footer">
        <div className="glass-panel rounded-[28px] px-6 py-6 sm:px-8">
          <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-3">
              {/*
                \u2500\u2500 Munchy Footer Logo Placeholder \u2500\u2500
                Replace the <div> below with an <img> tag for your footer logo:
                  <img src=\"/assets/munchy-logo.png\" alt=\"Munchy\" className=\"h-10 w-10 rounded-xl\" />
              */}
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-[#FF8C00] to-[#FFB347] text-white" data-testid="footer-logo-icon">
                <Utensils className="h-5 w-5" />
              </div>
              <div>
                <p className="text-lg font-semibold munchy-gradient-text">Munchy</p>
                <p className="text-xs text-[var(--app-text-muted)]">Snap, Scan & Track</p>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-4 text-sm">
              <a
                className="flex items-center gap-2 rounded-full border border-[rgba(255,140,0,0.12)] bg-white/80 px-4 py-2 text-[var(--app-text-soft)] hover:bg-white hover:text-[var(--app-primary)] transition-colors duration-200"
                data-testid="footer-contact-email"
                href="mailto:supportmunchyapp@gmail.com"
              >
                <Mail className="h-4 w-4" />
                supportmunchyapp@gmail.com
              </a>
              <a
                className="flex items-center gap-2 rounded-full border border-[rgba(50,205,50,0.15)] bg-white/80 px-4 py-2 text-[var(--app-text-soft)] hover:bg-white hover:text-[var(--app-secondary)] transition-colors duration-200"
                data-testid="footer-community-link"
                href="https://t.me/MunchyCommunity"
                target="_blank"
                rel="noopener noreferrer"
              >
                <MessageCircle className="h-4 w-4" />
                Join the Munchy Community
              </a>
            </div>
          </div>
          <div className="mt-5 border-t border-[rgba(255,140,0,0.08)] pt-4 text-center text-xs text-[var(--app-text-muted)]">
            {"\u00A9"} 2026 Munchy. All rights reserved. Made with {"\uD83C\uDF4A"} for food lovers everywhere.
          </div>
        </div>
      </footer>
    </div>
  );
};
