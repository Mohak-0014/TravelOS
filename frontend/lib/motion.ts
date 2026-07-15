import type { Transition, Variants } from "framer-motion";

/**
 * Shared motion vocabulary for the "Night Flight" redesign. Kept small and
 * reused everywhere instead of each page hand-rolling its own easing/timing —
 * motion should read as one cinematic system, not a pile of one-off tweens.
 */

export const EASE = [0.22, 1, 0.36, 1] as const;

export const DUR = {
  fast: 0.2,
  base: 0.35,
  slow: 0.5,
} as const;

/** Pass to `viewport` on a `whileInView` element to animate once, slightly early. */
export const viewportOnce = { once: true, margin: "-80px" } as const;

/** Springy layoutId transition for active-state pills (day nav, tabs). */
export const springPill: Transition = { type: "spring", damping: 30, stiffness: 340 };

/** Standard fade + rise-in. Use for cards, list items, section reveals. */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: DUR.base, ease: EASE } },
};

/** Plain opacity fade — for elements where vertical motion would be distracting. */
export const fade: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: DUR.base, ease: EASE } },
};

/** Wraps children with a staggered reveal. Pair with `fadeUp`/`fade` on each child. */
export function stagger(staggerDelay = 0.08, delayChildren = 0): Variants {
  return {
    hidden: {},
    show: {
      transition: { staggerChildren: staggerDelay, delayChildren },
    },
  };
}

/** Directional slide for wizard-style step transitions (AnimatePresence custom=direction). */
export function slideX(direction: 1 | -1): Variants {
  return {
    enter: { opacity: 0, x: direction > 0 ? 24 : -24 },
    center: { opacity: 1, x: 0, transition: { duration: DUR.base, ease: EASE } },
    exit: { opacity: 0, x: direction > 0 ? -24 : 24, transition: { duration: DUR.fast, ease: EASE } },
  };
}

/** SVG stroke draw-on — pair with `pathLength` on the target path/line. */
export const drawPath: Variants = {
  hidden: { pathLength: 0, opacity: 0 },
  show: { pathLength: 1, opacity: 1, transition: { duration: 1.1, ease: EASE } },
};

/**
 * Masked word-by-word headline reveal. Wrap each word in an outer span with
 * `overflow-hidden` + an inner motion.span using this variant, all inside a
 * stagger() container. The word slides up from behind its own mask.
 */
export const wordReveal: Variants = {
  hidden: { y: "110%" },
  show: { y: 0, transition: { duration: 0.7, ease: EASE } },
};

/** Soft scale-in for hero imagery and large decorative blocks. */
export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 1.06 },
  show: { opacity: 1, scale: 1, transition: { duration: 1.1, ease: EASE } },
};
