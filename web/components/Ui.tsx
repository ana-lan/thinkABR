import type { ReactNode } from "react";

export function Section({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20 border-t border-line py-12 sm:py-14">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-accent mb-2">{eyebrow}</p>
      <h2 className="text-2xl sm:text-[28px] font-semibold tracking-tight text-heading mb-6 max-w-3xl">
        {title}
      </h2>
      {children}
    </section>
  );
}

export function Note({ children }: { children: ReactNode }) {
  return <p className="mt-5 text-sm text-muted leading-relaxed border-l-2 border-accent pl-3 max-w-3xl">{children}</p>;
}

export function Stat({ value, label, accent = false }: { value: string; label: string; accent?: boolean }) {
  return (
    <div className="rounded-lg border border-line bg-panel p-4">
      <div className={`text-2xl font-semibold tabular-nums tracking-tight ${accent ? "text-accent" : "text-heading"}`}>
        {value}
      </div>
      <div className="text-xs text-subtle mt-1">{label}</div>
    </div>
  );
}