"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { Compass, Mail, Lock, User, ArrowRight } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { Token, UserOut } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { EASE } from "@/lib/motion";

const TAGLINES = ["Gets smarter every trip.", "Remembers what you love.", "Plans so you don't have to.", "Your AI travel companion."];

// Public Unsplash CDN — the panel keeps a designed gradient fallback underneath,
// so a failed/slow fetch never shows a hole.
const PANEL_PHOTO = "https://images.unsplash.com/photo-1502602898657-3e91760cbb34?q=80&w=1400&auto=format&fit=crop";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tagline] = useState(() => TAGLINES[Math.floor(Date.now() / 5000) % TAGLINES.length]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "register") {
        await api.post("/api/v1/auth/register", { email, password, full_name: fullName });
      }
      const tokenData = await api.post<Token>("/api/v1/auth/login", { email, password });
      const user = await api.get<UserOut>("/api/v1/auth/me", undefined, tokenData.access_token);
      setAuth(tokenData.access_token, user);
      router.push(mode === "register" ? "/onboarding" : "/trips");
    } catch (err) {
      if (err instanceof ApiError) {
        const detail = err.detail as { message?: string } | null;
        setError(detail?.message ?? `Error ${err.status}`);
      } else {
        setError("Something went wrong. Is the backend running?");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative min-h-screen flex bg-paper">
      {/* ── Photo panel — desktop only ── */}
      <div className="hidden lg:block relative w-[46%] overflow-hidden">
        {/* Fallback: warm dusk gradient */}
        <div
          className="absolute inset-0"
          style={{
            background:
              "radial-gradient(100% 70% at 30% 100%, rgba(255,125,80,0.25) 0%, transparent 60%), linear-gradient(200deg, #101825 0%, #1A1E28 60%, #221A18 100%)",
          }}
        />
        <div className="absolute inset-0 kenburns bg-cover bg-center" style={{ backgroundImage: `url(${PANEL_PHOTO})` }} />
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/25 to-black/30" />
        {/* Right edge blend into the page background */}
        <div className="absolute inset-y-0 right-0 w-32 bg-gradient-to-l from-paper to-transparent" />

        <div className="absolute inset-0 flex flex-col justify-between p-10 z-10">
          <span className="font-mono text-[10px] tracking-widest text-white/45">48.86°N 2.35°E · PARIS</span>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3, duration: 0.7, ease: EASE }}
          >
            <p className="font-display italic text-3xl xl:text-4xl text-white leading-snug max-w-sm mb-4">
              The world is waiting.
              <br />
              Start where you are.
            </p>
            <p className="font-mono text-[10px] uppercase tracking-[0.25em] text-white/50">TravelOS · Night Flight</p>
          </motion.div>
        </div>
      </div>

      {/* ── Form side ── */}
      <div className="relative flex-1 flex items-center justify-center px-4 py-16">
        {/* Faint warm bloom behind the form */}
        <div
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[560px] h-[560px] rounded-full pointer-events-none"
          style={{ background: "radial-gradient(circle, rgba(255,158,100,0.07) 0%, transparent 65%)" }}
        />
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: EASE }}
          className="relative z-10 w-full max-w-sm"
        >
          {/* Logo + brand */}
          <div className="text-center mb-8">
            <div className="inline-flex w-12 h-12 rounded-xl bg-sunset items-center justify-center mb-4 shadow-glow">
              <Compass className="w-6 h-6 text-[#1F1206]" />
            </div>
            <h1 className="font-display text-3xl font-medium text-ink-900 mb-1">TravelOS</h1>
            <p className="text-sm text-ink-400" suppressHydrationWarning>
              {tagline}
            </p>
          </div>

          <div className="glass rounded-xl p-7">
            {/* Mode toggle */}
            <div className="flex rounded-lg bg-ink-100 p-1 mb-6">
              {(["login", "register"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => {
                    setMode(m);
                    setError(null);
                  }}
                  className={`flex-1 py-2 rounded-md text-sm font-medium transition-colors duration-150 ${
                    mode === m ? "bg-surface-raised border border-ink-900/10 text-ink-900" : "text-ink-400 hover:text-ink-600"
                  }`}
                >
                  {m === "login" ? "Sign In" : "Register"}
                </button>
              ))}
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <AnimatePresence mode="wait">
                {mode === "register" && (
                  <motion.div
                    key="name"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.25 }}
                  >
                    <Input icon={User} type="text" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Full name" />
                  </motion.div>
                )}
              </AnimatePresence>

              <Input icon={Mail} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email address" />

              <Input
                icon={Lock}
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
              />

              <AnimatePresence>
                {error && (
                  <motion.p
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="text-sm text-danger bg-danger-tint border border-danger/20 rounded-lg px-4 py-3"
                  >
                    {error}
                  </motion.p>
                )}
              </AnimatePresence>

              <Button type="submit" loading={loading} iconRight={ArrowRight}>
                {mode === "login" ? "Sign in" : "Create account"}
              </Button>
            </form>
          </div>

          <p className="text-center text-xs text-ink-400 mt-4">The travel planning system that remembers you.</p>
        </motion.div>
      </div>
    </div>
  );
}
