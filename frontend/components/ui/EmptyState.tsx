import type { LucideIcon } from "lucide-react";

export interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  body?: string;
  action?: React.ReactNode;
}

export function EmptyState({ icon: Icon, title, body, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center text-center gap-3 py-12 px-6">
      <div className="w-11 h-11 rounded-full bg-ink-100 flex items-center justify-center">
        <Icon className="w-5 h-5 text-ink-400" />
      </div>
      <div>
        <p className="font-display text-lg font-medium text-ink-900">{title}</p>
        {body && <p className="text-sm text-ink-400 mt-1 max-w-xs">{body}</p>}
      </div>
      {action}
    </div>
  );
}
