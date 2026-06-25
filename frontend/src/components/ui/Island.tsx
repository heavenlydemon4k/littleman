import { forwardRef } from "react";
import type { ElementType, HTMLAttributes, ReactNode } from "react";
import clsx from "clsx";

/**
 * Island — the shared rounded/floating surface primitive.
 *
 * Centralizes the look that was repeated as `rounded-xl border border-border bg-surface-*`
 * across the chat bar, skills popover, and activity feed. Tune the radius/shadow once via the
 * `--island-*` tokens in index.css (exposed as Tailwind's `rounded-island` / `shadow-island`).
 *
 * Variants:
 *  - `surface`     bg level (1 = deeper/nested, 2 = raised; default 2)
 *  - `floating`    adds the island drop shadow (popovers, the live feed) — gives the "lifts off
 *                  the page" feel; omit for inset/nested islands
 *  - `interactive` accent focus-within ring (used by the input bar)
 */
export interface IslandProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType;
  surface?: 1 | 2;
  floating?: boolean;
  interactive?: boolean;
  children?: ReactNode;
}

export const Island = forwardRef<HTMLElement, IslandProps>(function Island(
  { as: Tag = "div", surface = 2, floating = false, interactive = false, className, children, ...rest },
  ref,
) {
  return (
    <Tag
      ref={ref}
      className={clsx(
        "rounded-island border border-border",
        surface === 1 ? "bg-surface-1" : "bg-surface-2",
        floating && "shadow-island",
        interactive && "transition-colors focus-within:border-blue-500",
        className,
      )}
      {...rest}
    >
      {children}
    </Tag>
  );
});
