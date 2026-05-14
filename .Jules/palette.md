## 2024-05-12 - Missing ARIA Labels in Call Recording Player
**Learning:** Found an accessibility issue pattern in the app's static files where icon-only buttons for the call recording player (Play, Fast Backward, Fast Forward) lacked `aria-label` attributes, making them inaccessible to screen readers.
**Action:** Always verify that icon-only buttons have descriptive `aria-label` attributes to ensure they are screen reader friendly.

## 2026-05-11 - [UX Improvement] Add disabled state and default type to reusable Button
**Learning:** Reusable button components without explicit disabled styling make it impossible for users to know if an action is currently unavailable. Similarly, omitting `type="button"` defaults standard buttons to `type="submit"` within a `<form>` element, causing unintended form submissions and page reloads.
**Action:** Always include a visual indicator for disabled buttons (`disabled:cursor-not-allowed disabled:opacity-50`) and default custom button components to `type="button"` unless they are explicitly meant for submission.

## 2026-05-13 - Focus Styles vs Focus-Visible
**Learning:** Using `focus:ring` on buttons creates a noticeable and sometimes distracting outline when users simply click with a mouse, even though it's primarily meant for keyboard navigation.
**Action:** Replace `focus:` pseudo-class with `focus-visible:` for focus rings (e.g., `focus-visible:ring-amberline`) in interactive components like `Button`. This ensures keyboard users still get clear, accessible focus indicators (using the standard amberline color) while mouse and touch users get a cleaner, undisturbed click experience.
