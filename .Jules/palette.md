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

## 2024-05-15 - Semantic Lists and Tactile Feedback
**Learning:** Generic wrappers like `<div>` or `<section>` for lists of items obscure content structure for screen readers. Using standard interactive components like buttons without tactile feedback (`active:` states) makes interfaces feel unresponsive.
**Action:** Always use semantic `<ul>` or `<ol>` tags with descriptive `aria-label`s for lists of items to ensure they are properly parsed and announced by screen readers. For interactive elements like buttons, include a subtle tactile feedback (e.g., `active:scale-[0.98]`) to improve perceived responsiveness and the overall interactive feel.

## $(date +%Y-%m-%d) - [UX Improvement] Add accessible loading state to Button
**Learning:** Found that the primary UI Button lacked a standardized, built-in loading state. Without this, developers might omit visual feedback during async operations, leading to poor UX and potential double-submissions.
**Action:** Always provide an \`isLoading\` prop on core button components that not only renders a spinner but automatically sets \`disabled\` and \`aria-disabled\` attributes to gracefully handle the pending state.

## 2026-05-16 - [UX Improvement] Add disabled tooltip and aria-busy to Button
**Learning:** Disabled buttons do not trigger hover tooltips (titles) or receive keyboard focus by default because they don't fire pointer/focus events. Furthermore, loading states lack semantic meaning without `aria-busy`.
**Action:** When providing a reason for a disabled button (`disabledReason`), wrap it in a focusable `<span>` (`tabIndex={0}`) with `cursor-not-allowed`, and set `pointer-events-none` on the button itself so the wrapper can show the title. Always add `aria-busy={isLoading}` for screen readers.
