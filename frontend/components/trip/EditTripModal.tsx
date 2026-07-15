"use client";

import { useState, useEffect } from "react";
import type { TripOut, TripUpdate } from "@/lib/api";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";

function formFromTrip(trip: TripOut): TripUpdate {
  return {
    title: trip.title,
    destination_city: trip.destination_city,
    destination_country: trip.destination_country ?? "",
    start_date: trip.start_date,
    end_date: trip.end_date,
    num_travelers: trip.num_travelers,
    budget_total: trip.budget_total ?? undefined,
    budget_currency: trip.budget_currency,
  };
}

export function EditTripModal({
  open,
  trip,
  onClose,
  onSave,
}: {
  open: boolean;
  trip: TripOut;
  onClose: () => void;
  onSave: (updates: TripUpdate) => Promise<void>;
}) {
  const [form, setForm] = useState<TripUpdate>(() => formFromTrip(trip));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modal stays mounted so Modal's exit animation can play — resync the form
  // from the latest trip each time it's reopened (a plain useState initializer
  // would only run once, on first mount).
  useEffect(() => {
    if (open) setForm(formFromTrip(trip));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const set = (key: keyof TripUpdate, value: unknown) => setForm((f) => ({ ...f, [key]: value }));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await onSave(form);
      onClose();
    } catch {
      setError("Could not save changes. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Edit Trip" width="sm">
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="text-xs text-ink-400 mb-1 block">Trip name</label>
          <Input value={form.title ?? ""} onChange={(e) => set("title", e.target.value)} required />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-ink-400 mb-1 block">City</label>
            <Input value={form.destination_city ?? ""} onChange={(e) => set("destination_city", e.target.value)} required />
          </div>
          <div>
            <label className="text-xs text-ink-400 mb-1 block">Country</label>
            <Input
              placeholder="Optional"
              value={form.destination_country ?? ""}
              onChange={(e) => set("destination_country", e.target.value || null)}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-ink-400 mb-1 block">Start date</label>
            <Input type="date" value={form.start_date ?? ""} onChange={(e) => set("start_date", e.target.value)} required />
          </div>
          <div>
            <label className="text-xs text-ink-400 mb-1 block">End date</label>
            <Input type="date" value={form.end_date ?? ""} onChange={(e) => set("end_date", e.target.value)} required />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-ink-400 mb-1 block">Travelers</label>
            <Input
              type="number"
              min={1}
              max={20}
              value={form.num_travelers ?? 1}
              onChange={(e) => set("num_travelers", parseInt(e.target.value))}
              required
            />
          </div>
          <div>
            <label className="text-xs text-ink-400 mb-1 block">Budget</label>
            <Input
              type="number"
              min={0}
              placeholder="Optional"
              value={form.budget_total ?? ""}
              onChange={(e) => set("budget_total", e.target.value ? parseFloat(e.target.value) : null)}
            />
          </div>
        </div>

        <div>
          <label className="text-xs text-ink-400 mb-1 block">Currency</label>
          <Input
            className="uppercase"
            maxLength={3}
            value={form.budget_currency ?? "INR"}
            onChange={(e) => set("budget_currency", e.target.value.toUpperCase())}
          />
        </div>

        {error && <p className="text-xs text-danger">{error}</p>}

        <div className="flex gap-3 pt-1">
          <Button type="button" variant="secondary" onClick={onClose} className="flex-1 justify-center">
            Cancel
          </Button>
          <Button type="submit" loading={saving} className="flex-1 justify-center">
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
