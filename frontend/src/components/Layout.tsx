import Link from "next/link";
import { useRouter } from "next/router";
import { FileText, Upload, LayoutDashboard, Zap } from "lucide-react";
import { cn } from "@/utils";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/upload", label: "Upload", icon: Upload },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { pathname } = useRouter();

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--surface)" }}>
      {/* Top nav */}
      <header
        className="border-b sticky top-0 z-50 backdrop-blur-md"
        style={{
          borderColor: "var(--border)",
          background: "rgba(14,15,20,0.85)",
        }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 group">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center ring-pulse"
              style={{ background: "var(--accent)" }}
            >
              <Zap size={14} className="text-white" />
            </div>
            <span
              className="font-bold text-lg tracking-tight"
              style={{ fontFamily: "'Space Grotesk', sans-serif", color: "var(--text)" }}
            >
              Doc<span style={{ color: "var(--accent)" }}>Flow</span>
            </span>
          </Link>

          {/* Nav links */}
          <nav className="flex items-center gap-1">
            {NAV.map(({ href, label, icon: Icon }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className={cn(
                    "flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all",
                    active
                      ? "text-white"
                      : "hover:text-white"
                  )}
                  style={{
                    background: active ? "var(--surface-3)" : "transparent",
                    color: active ? "var(--text)" : "var(--muted)",
                    border: active ? "1px solid var(--border)" : "1px solid transparent",
                  }}
                >
                  <Icon size={15} />
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 py-8">
        {children}
      </main>

      {/* Footer */}
      <footer
        className="border-t text-center py-4 text-xs"
        style={{ borderColor: "var(--border)", color: "var(--muted)" }}
      >
        DocFlow — Async Document Processing System
      </footer>
    </div>
  );
}
