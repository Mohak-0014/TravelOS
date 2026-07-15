"use client";

import { useState } from "react";
import { ArrowRight } from "lucide-react";
import type { ApprovalOut } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";

export type OnDecision = (id: string, decision: "approved" | "rejected", resolutionNote?: string) => void;

// ── ConciergeSwapCard ──────────────────────────────────────────────────────────

function ConciergeSwapCard({ approval, onDecision }: { approval: ApprovalOut; onDecision: OnDecision }) {
  const a = approval;
  const alternatives = (a.payload.alternatives as Array<{ title: string; description: string }> | undefined) ?? [];
  const [selectedAlt, setSelectedAlt] = useState(0);
  const current = a.payload.current as { title: string; item_type?: string; start_time?: string; est_cost?: number };
  const chosen = alternatives[selectedAlt] ?? (a.payload.replacement as { title: string; description?: string });

  return (
    <Card>
      <div className="flex items-center gap-2 mb-3">
        <Badge tone="accent">AI Concierge</Badge>
        <span className="text-[10px] text-ink-400">Suggestion · Day {a.payload.day as number}</span>
      </div>

      {/* Before → After diff */}
      <div className="flex items-start gap-2 mb-3">
        <div className="flex-1 p-2.5 rounded-lg bg-ink-100">
          <p className="text-[10px] text-ink-400 mb-0.5">Current</p>
          <p className="text-xs text-ink-400 line-through leading-snug">{current.title}</p>
          {current.start_time && <p className="font-mono text-[10px] text-ink-300 mt-0.5">{current.start_time.slice(0, 5)}</p>}
          {current.est_cost != null && <p className="font-mono text-[10px] text-ink-300">{current.est_cost}</p>}
        </div>
        <ArrowRight className="w-3.5 h-3.5 text-ink-300 shrink-0 mt-3.5" />
        <div className="flex-1 p-2.5 rounded-lg bg-accent-tint">
          <p className="text-[10px] text-accent mb-0.5">Proposed</p>
          <p className="text-xs text-ink-900 font-medium leading-snug">{chosen.title}</p>
          {chosen.description && <p className="text-[10px] text-ink-400 line-clamp-2 mt-0.5">{chosen.description}</p>}
        </div>
      </div>

      {/* Alternatives selector */}
      {alternatives.length > 1 && (
        <div className="mb-3 space-y-1.5">
          <p className="font-mono text-[10px] text-ink-400 uppercase tracking-wider">Choose an option</p>
          {alternatives.map((alt, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedAlt(idx)}
              className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors border ${
                idx === selectedAlt
                  ? "bg-accent-tint border-accent/30 text-ink-900"
                  : "bg-ink-100 border-transparent text-ink-400 hover:bg-ink-100/70"
              }`}
            >
              <span className="font-medium">{alt.title}</span>
              {alt.description && <span className="text-[10px] text-ink-400 block line-clamp-1 mt-0.5">{alt.description}</span>}
            </button>
          ))}
        </div>
      )}

      {!!a.payload.reason && <p className="text-xs text-ink-400 italic mb-4">{a.payload.reason as string}</p>}

      <div className="flex gap-2">
        <Button size="sm" onClick={() => onDecision(a.id, "approved", alternatives.length > 1 ? `alt:${selectedAlt}` : undefined)}>
          Accept swap
        </Button>
        <Button size="sm" variant="secondary" onClick={() => onDecision(a.id, "rejected")}>
          Keep original
        </Button>
      </div>
    </Card>
  );
}

// ── ConciergeAddCard ───────────────────────────────────────────────────────────

function ConciergeAddCard({ approval, onDecision }: { approval: ApprovalOut; onDecision: OnDecision }) {
  const a = approval;
  return (
    <Card>
      <div className="flex items-center gap-2 mb-2">
        <Badge tone="accent">AI Concierge</Badge>
        <span className="text-[10px] text-ink-400">Day {a.payload.day as number} · Add</span>
      </div>
      <p className="font-medium text-ink-900 text-sm leading-snug mb-0.5">{a.payload.title as string}</p>
      {!!a.payload.description && <p className="text-xs text-ink-400 line-clamp-2 mb-1">{a.payload.description as string}</p>}
      {!!a.payload.reason && <p className="text-xs text-ink-400 italic mb-4">{a.payload.reason as string}</p>}
      <div className="flex gap-2">
        <Button size="sm" onClick={() => onDecision(a.id, "approved")}>
          Add to itinerary
        </Button>
        <Button size="sm" variant="secondary" onClick={() => onDecision(a.id, "rejected")}>
          No thanks
        </Button>
      </div>
    </Card>
  );
}

// ── ApprovalCard (dispatcher) ──────────────────────────────────────────────────

export function ApprovalCard({ approval, onDecision }: { approval: ApprovalOut; onDecision: OnDecision }) {
  const a = approval;

  if (a.change_type === "event_add") {
    return (
      <Card>
        <div className="flex gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 mb-1">
              <Badge tone={a.payload.source === "ticketmaster" ? "info" : "warning"}>
                {a.payload.source === "ticketmaster" ? "Ticketmaster" : "Eventbrite"}
              </Badge>
              <span className="text-[10px] text-ink-400">{a.payload.category as string}</span>
            </div>
            <p className="font-medium text-ink-900 text-sm leading-snug">{a.payload.event_name as string}</p>
            <p className="text-xs text-ink-400 mt-0.5">
              Day {a.payload.day_number as number} · {a.payload.venue_name as string}
            </p>
            {!!a.payload.start_time && <p className="text-xs text-ink-300 font-mono">{String(a.payload.start_time)}</p>}
            {a.payload.price_min != null && (
              <p className="text-xs text-accent mt-0.5 font-medium font-mono">
                {a.payload.price_currency as string} {(a.payload.price_min as number).toFixed(0)}
                {a.payload.price_max !== a.payload.price_min ? `–${(a.payload.price_max as number).toFixed(0)}` : ""}
              </p>
            )}
            <p className="text-xs text-ink-400 mt-1.5 line-clamp-2">{a.summary}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 mt-4">
          <Button size="sm" onClick={() => onDecision(a.id, "approved")}>
            Add to itinerary
          </Button>
          <Button size="sm" variant="secondary" onClick={() => onDecision(a.id, "rejected")}>
            Skip
          </Button>
          {!!a.payload.url && (
            <a
              href={String(a.payload.url)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-accent hover:underline ml-auto"
            >
              View ↗
            </a>
          )}
        </div>
      </Card>
    );
  }

  if (a.change_type === "budget_swap") {
    return (
      <Card>
        <div className="flex items-center gap-2 mb-2">
          <Badge tone="danger">Over Budget</Badge>
          <span className="text-[10px] text-ink-400">Budget Optimizer</span>
        </div>
        <div className="space-y-1 mb-3">
          <div className="flex items-center gap-2 text-xs text-ink-400">
            <span className="line-through">
              {(a.payload.current as { title: string }).title}
              {a.payload.est_cost_original != null
                ? ` · ${a.payload.currency as string} ${(a.payload.est_cost_original as number).toFixed(0)}`
                : ""}
            </span>
            <ArrowRight className="w-3 h-3 text-ink-300 shrink-0" />
            <span className="text-ink-900 font-medium">{(a.payload.replacement as { title: string }).title}</span>
          </div>
          {(a.payload.replacement as { description?: string }).description && (
            <p className="text-xs text-ink-400 line-clamp-2">{(a.payload.replacement as { description: string }).description}</p>
          )}
        </div>
        <p className="text-xs text-ink-400 italic mb-4">{a.payload.reason as string}</p>
        <div className="flex gap-2">
          <Button size="sm" onClick={() => onDecision(a.id, "approved")}>
            Accept swap
          </Button>
          <Button size="sm" variant="secondary" onClick={() => onDecision(a.id, "rejected")}>
            Keep original
          </Button>
        </div>
      </Card>
    );
  }

  if (a.change_type === "budget_upgrade") {
    return (
      <Card>
        <div className="flex items-center gap-2 mb-2">
          <Badge tone="success">Under Budget</Badge>
          <span className="text-[10px] text-ink-400">Budget Optimizer</span>
          {a.payload.budget_remaining != null && (
            <span className="text-[10px] text-ink-400 ml-auto font-mono">
              {a.payload.currency as string} {(a.payload.budget_remaining as number).toFixed(0)} remaining
            </span>
          )}
        </div>
        <p className="font-medium text-ink-900 text-sm mb-0.5">{String(a.payload.title ?? "")}</p>
        {!!a.payload.description && <p className="text-xs text-ink-400 line-clamp-2 mb-1">{String(a.payload.description)}</p>}
        <p className="text-xs text-ink-400 italic mb-4">{String(a.payload.reason ?? "")}</p>
        <div className="flex gap-2">
          <Button size="sm" onClick={() => onDecision(a.id, "approved")}>
            Sounds great
          </Button>
          <Button size="sm" variant="secondary" onClick={() => onDecision(a.id, "rejected")}>
            Not interested
          </Button>
        </div>
      </Card>
    );
  }

  if (a.change_type === "concierge_swap") {
    return <ConciergeSwapCard approval={a} onDecision={onDecision} />;
  }

  if (a.change_type === "concierge_add") {
    return <ConciergeAddCard approval={a} onDecision={onDecision} />;
  }

  // Generic fallback
  return (
    <Card>
      <p className="font-mono text-[10px] text-accent uppercase tracking-wider mb-1 font-medium">{a.change_type.replace(/_/g, " ")}</p>
      <p className="text-sm text-ink-600 mb-4">{a.summary}</p>
      <div className="flex gap-2">
        <Button size="sm" onClick={() => onDecision(a.id, "approved")}>
          Approve
        </Button>
        <Button size="sm" variant="secondary" onClick={() => onDecision(a.id, "rejected")}>
          Reject
        </Button>
      </div>
    </Card>
  );
}
