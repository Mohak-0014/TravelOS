import {
  Clock,
  Loader2,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  X,
  Activity,
  Utensils,
  Bus,
  Hotel,
  Sun,
  Landmark,
  Mountain,
  Leaf,
  Moon,
  Palette,
  BookOpen,
  Heart,
  Globe,
  Sandwich,
  UtensilsCrossed,
  Salad,
  Sprout,
  Fish,
  CircleCheck,
  BadgeCheck,
  type LucideIcon,
} from "lucide-react";

type Tone = "neutral" | "accent" | "success" | "warning" | "danger" | "info";

// ── Trip status (unified — was duplicated across trips/page, [tripId]/page, profile) ──

export const STATUS_CONFIG: Record<string, { label: string; tone: Tone; icon: LucideIcon }> = {
  planning: { label: "Planning", tone: "warning", icon: Clock },
  generating: { label: "Generating…", tone: "info", icon: Loader2 },
  awaiting_approval: { label: "Your Call", tone: "danger", icon: AlertCircle },
  planned: { label: "Ready", tone: "success", icon: CheckCircle2 },
  failed: { label: "Failed", tone: "danger", icon: AlertTriangle },
  cancelled: { label: "Cancelled", tone: "neutral", icon: X },
  completed: { label: "Completed", tone: "neutral", icon: CheckCircle2 },
};

// ── Itinerary item type icons (was ITEM_ICONS, emoji dropped for lucide-only) ──

export const ITEM_ICONS: Record<string, { icon: LucideIcon; tone: Tone }> = {
  activity: { icon: Activity, tone: "accent" },
  meal: { icon: Utensils, tone: "warning" },
  transport: { icon: Bus, tone: "info" },
  lodging: { icon: Hotel, tone: "neutral" },
  free: { icon: Sun, tone: "neutral" },
};

// ── Onboarding / profile preference options (values are API payloads — ids
// must stay byte-identical to what the backend expects) ──────────────────

export const INTERESTS: { id: string; label: string; icon: LucideIcon }[] = [
  { id: "culture", label: "Culture", icon: Landmark },
  { id: "adventure", label: "Adventure", icon: Mountain },
  { id: "food", label: "Food & Drink", icon: Utensils },
  { id: "nature", label: "Nature", icon: Leaf },
  { id: "nightlife", label: "Nightlife", icon: Moon },
  { id: "art", label: "Art & Museums", icon: Palette },
  { id: "history", label: "History", icon: BookOpen },
  { id: "wellness", label: "Wellness", icon: Heart },
];

export const FOOD_PREFS: { id: string; label: string; icon: LucideIcon }[] = [
  { id: "local_cuisine", label: "Local Cuisine", icon: Globe },
  { id: "street_food", label: "Street Food", icon: Sandwich },
  { id: "fine_dining", label: "Fine Dining", icon: UtensilsCrossed },
  { id: "vegetarian", label: "Vegetarian", icon: Salad },
  { id: "vegan", label: "Vegan", icon: Sprout },
  { id: "seafood", label: "Seafood", icon: Fish },
  { id: "halal", label: "Halal", icon: CircleCheck },
  { id: "kosher", label: "Kosher", icon: BadgeCheck },
];

// ── sessionStorage key builders (centralized so writer/reader can't drift) ──

export const genStartKey = (tripId: string) => `gen_start_${tripId}`;
export const flightOriginKey = (tripId: string) => `flight_origin_${tripId}`;
