"use client";

import { Component, ReactNode, useEffect, useState } from "react";
import dynamic from "next/dynamic";

// ── CSS fallback (no WebGL / SSR) ─────────────────────────────────────────────

function StarFieldCSS({ className = "" }: { className?: string }) {
  return (
    <div
      className={`absolute inset-0 pointer-events-none ${className}`}
      style={{
        zIndex: 0,
        background: [
          "radial-gradient(ellipse at 20% 30%, rgba(59,130,246,0.06) 0%, transparent 60%)",
          "radial-gradient(ellipse at 80% 70%, rgba(139,92,246,0.05) 0%, transparent 50%)",
        ].join(", "),
      }}
    />
  );
}

// ── Error boundary wrapping the dynamic Three.js canvas ───────────────────────

class ThreeBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { failed: false };
  }
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed) return <StarFieldCSS />;
    return this.props.children;
  }
}

// ── Dynamically load Three.js canvas only when WebGL is available ─────────────

const StarFieldWebGL = dynamic(
  () =>
    import("./StarFieldWebGL").catch(() => ({
      default: StarFieldCSS,
    })),
  { ssr: false, loading: () => <StarFieldCSS /> }
);

// ── Public API ────────────────────────────────────────────────────────────────

export default function StarField({ className = "" }: { className?: string }) {
  const [webgl, setWebgl] = useState<boolean | null>(null);

  useEffect(() => {
    try {
      const canvas = document.createElement("canvas");
      const ctx =
        canvas.getContext("webgl") ?? canvas.getContext("experimental-webgl");
      setWebgl(!!ctx);
    } catch {
      setWebgl(false);
    }
  }, []);

  // During SSR / before hydration: show CSS
  if (webgl === null || !webgl) return <StarFieldCSS className={className} />;

  return (
    <ThreeBoundary>
      <StarFieldWebGL className={className} />
    </ThreeBoundary>
  );
}
