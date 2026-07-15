"use client";

import { useRef } from "react";
import { motion, useMotionValue, useSpring, useTransform, type HTMLMotionProps } from "framer-motion";
import { cn } from "@/lib/ui";

export interface TiltCardProps extends Omit<HTMLMotionProps<"div">, "children"> {
  /** Max rotation in degrees. */
  intensity?: number;
  /** Adds a soft cursor-following highlight — used for large decorative cards. */
  glow?: boolean;
  children?: React.ReactNode;
}

/** Wraps children with a mouse-tracked 3D tilt. Shared by destination cards,
 * trip cards, and feature cards so the physics feel identical everywhere. */
export function TiltCard({ intensity = 6, glow = false, className, children, ...props }: TiltCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0.5);
  const y = useMotionValue(0.5);
  const spring = { damping: 24, stiffness: 280, mass: 0.6 };
  const rotateX = useSpring(useTransform(y, [0, 1], [intensity, -intensity]), spring);
  const rotateY = useSpring(useTransform(x, [0, 1], [-intensity, intensity]), spring);
  const glowX = useTransform(x, [0, 1], ["10%", "90%"]);
  const glowY = useTransform(y, [0, 1], ["10%", "90%"]);
  const glowBackground = useTransform([glowX, glowY], ([gx, gy]) => `radial-gradient(220px circle at ${gx} ${gy}, rgba(255,255,255,0.16), transparent 70%)`);

  function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    x.set((e.clientX - rect.left) / rect.width);
    y.set((e.clientY - rect.top) / rect.height);
  }
  function handleMouseLeave() {
    x.set(0.5);
    y.set(0.5);
  }

  return (
    <motion.div
      ref={ref}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      style={{ rotateX, rotateY, transformStyle: "preserve-3d", perspective: 800 }}
      className={cn("relative", className)}
      {...props}
    >
      {glow && (
        <motion.div
          className="absolute inset-0 opacity-0 hover:opacity-100 transition-opacity duration-300 pointer-events-none rounded-[inherit]"
          style={{ background: glowBackground }}
        />
      )}
      {children}
    </motion.div>
  );
}
