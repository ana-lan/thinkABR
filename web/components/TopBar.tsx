import { ThemeToggle } from "./ThemeToggle";
import { REPO_URL } from "@/lib/data";

const tabs = [
  { href: "#explorer", label: "Explorer" },
  { href: "#reasoning", label: "Reasoning" },
  { href: "#serving", label: "Serving" },
  { href: "#method", label: "Method" },
];

export function TopBar() {
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-bg/90 backdrop-blur">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-6">
        <a href="#top" className="flex items-baseline gap-2 shrink-0">
          <span className="font-semibold tracking-tight text-heading">ThinkABR</span>
          <span className="hidden lg:inline text-xs text-subtle">Inference cost workstation</span>
        </a>
        <nav className="hidden sm:flex flex-1 gap-5">
          {tabs.map((t) => (
            <a
              key={t.href}
              href={t.href}
              className="text-sm text-muted hover:text-heading border-b-2 border-transparent hover:border-accent pb-0.5 transition-colors whitespace-nowrap"
            >
              {t.label}
            </a>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-4 shrink-0">
          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            className="text-sm text-muted hover:text-heading transition-colors"
          >
            GitHub
          </a>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}