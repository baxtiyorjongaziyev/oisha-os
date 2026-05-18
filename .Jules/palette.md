## 2024-05-12 - Missing ARIA Labels in Call Recording Player
**Learning:** Found an accessibility issue pattern in the app's static files where icon-only buttons for the call recording player (Play, Fast Backward, Fast Forward) lacked `aria-label` attributes, making them inaccessible to screen readers.
**Action:** Always verify that icon-only buttons have descriptive `aria-label` attributes to ensure they are screen reader friendly.

## 2026-05-11 - [UX Improvement] Add disabled state and default type to reusable Button
**Learning:** Reusable button components without explicit disabled styling make it impossible for users to know if an action is currently unavailable. Similarly, omitting `type="button"` defaults standard buttons to `type="submit"` within a `<form>` element, causing unintended form submissions and page reloads.
**Action:** Always include a visual indicator for disabled buttons (`disabled:cursor-not-allowed disabled:opacity-50`) and default custom button components to `type="button"` unless they are explicitly meant for submission.

## 2026-05-13 - Focus Styles vs Focus-Visible
**Learning:** Using `focus:ring` on buttons creates a noticeable and sometimes distracting outline when users simply click with a mouse, even though it's primarily meant for keyboard navigation.
**Action:** Replace `focus:` pseudo-class with `focus-visible:` for focus rings (e.g., `focus-visible:ring-amberline`) in interactive components like `Button`. This ensures keyboard users still get clear, accessible focus indicators (using the standard amberline color) while mouse and touch users get a cleaner, undisturbed click experience.

## 2026-05-14 - Tailwind v4 Compatibility with config files
**Learning:** Tailwind CSS v4 relies on `@import "tailwindcss";` in `globals.css` and configuring `@tailwindcss/postcss` in PostCSS rather than traditional `.config.ts` files, unless specifically configured to use them via `@config` directives. When using legacy configuration objects, custom colors like `amberline` won't be available unless explicitly imported into the new v4 format.
**Action:** Always ensure any necessary custom theme variables like `--color-amberline: #d9922e;` or `@theme` blocks are properly configured for Tailwind v4 if the styling engine requires it.

## 2026-05-18 - Tactile Feedback and Semantic Lists
**Learning:** Users appreciate subtle visual feedback during interactions (like button presses), and screen readers require semantic HTML tags to correctly interpret content structure (like lists of features).
**Action:** Use `active:scale-[0.98]` on buttons for a smooth, tactile press effect. Always use semantic tags like `<ul>` and `<li>` with descriptive `aria-label` attributes instead of generic `<div>` elements for presenting lists.
