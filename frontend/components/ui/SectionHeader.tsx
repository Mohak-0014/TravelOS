export interface SectionHeaderProps {
  eyebrow: string;
  title?: string;
  action?: React.ReactNode;
  id?: string;
}

export function SectionHeader({ eyebrow, title, action, id }: SectionHeaderProps) {
  return (
    <div id={id} className="mb-4">
      <div className="flex items-center justify-between gap-4 mb-2">
        <span className="font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-ink-400">{eyebrow}</span>
        {action}
      </div>
      <div className="h-px bg-ink-900/10" />
      {title && <h2 className="font-display text-xl font-medium text-ink-900 mt-3">{title}</h2>}
    </div>
  );
}
