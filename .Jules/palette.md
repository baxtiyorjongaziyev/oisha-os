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

## 2026-05-24 - [UX Improvement] Add accessible loading state to Button

**Learning:** Found that the primary UI Button lacked a standardized, built-in loading state. Without this, developers might omit visual feedback during async operations, leading to poor UX and potential double-submissions.
**Action:** Always provide an `isLoading` prop on core button components that not only renders a spinner but automatically sets `disabled` and `aria-disabled` attributes to gracefully handle the pending state.

## 2026-05-24 - [UX Improvement] Additional accessibility for Button loading state

**Learning:** While the primary UI Button handled `disabled` and `aria-disabled` correctly during its loading state, it lacked `aria-busy` on the button itself and `aria-hidden="true"` on the loading SVG. This could cause screen readers to announce the SVG elements or fail to indicate that the component is actively processing a request.
**Action:** Always include `aria-busy={isLoading}` on components representing asynchronous states and ensure any decorative or visually repetitive loading indicators (like spinners) have `aria-hidden="true"` to prevent screen reader noise.

## 2026-05-16 - [UX Improvement] Add accessible tooltip for disabled buttons

**Learning:** Disabled buttons do not trigger hover tooltips (titles) or receive keyboard focus by default because they don't fire pointer/focus events. Furthermore, loading states lack semantic meaning without `aria-busy`.
**Action:** When providing a reason for a disabled button (`disabledReason`), wrap it in a focusable `<span>` (`tabIndex={0}`) with `cursor-not-allowed`, and set `pointer-events-none` on the button itself so the wrapper can show the title. Always add `aria-busy={isLoading}` for screen readers.

## 2026-05-25 - [UX Improvement] Add visual anchors to plain text lists

**Learning:** Presenting a list of features as plain text without visual anchors makes the content dense and hard to scan.
**Action:** Enhance plain text list items with subtle visual anchors, such as an inline SVG checkmark with `flex items-center gap-3`, to improve scannability and create a more pleasant reading experience.

## 2026-05-26 - [A11y Insight] Explicitly declaring state for screen readers during loading

**Learning:** When adding a visual loading spinner to a button component, screen readers don't automatically know the button is in a processing state just from a new SVG appearing.
**Action:** Always add `aria-busy={isLoading}` to the container element to explicitly announce the pending state, and add `aria-hidden="true"` to the decorative SVG spinner so screen readers don't read out irrelevant vector paths.

## 2026-05-29 - [UX Improvement] Focus styles for tooltips on disabled interactive elements

**Learning:** When using standard `focus-visible` styles on wrappers for disabled components (e.g., `<span tabIndex={0}>` acting as a tooltip wrapper for a disabled button), the focus ring forms a generic box around the wrapper, ignoring the child component's specific shape (like `rounded-full`).
**Action:** Always apply `group` and `focus:outline-none` to the wrapper, and use `group-focus-visible:ring-*` on the child element so the focus ring seamlessly inherits the child's exact shape and border-radius.

## 2024-10-25 - Custom Dropdown Accessibility Pattern
**Learning:** Custom UI dropdowns frequently lack native semantic structure. Wrapping loosely grouped `<button>` items in `<ul>`/`<li>` tags combined with `aria-labelledby` pointing to the trigger button's ID instantly transforms them into screen-reader-friendly menus. Furthermore, adding visual anchors (like an inline checkmark) for the `aria-current` item drastically improves scannability.
**Action:** Always wrap custom dropdown list items in `<ul>` and `<li>`, link them to their trigger via `aria-labelledby`, and ensure each option has robust `focus-visible:ring` styles rather than relying exclusively on hover states.
## 2026-06-25 - Consistent Keyboard Navigation
**Learning:** Hardcoded `focus:` styles (like `focus:ring-2`) trigger visually during mouse clicks, leading to an inconsistent UX. Many generic interactive elements omit focus indicators entirely relying on `focus:outline-none`.
**Action:** Always replace `focus:` with `focus-visible:` for focus rings (e.g. `focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1`) to ensure accessibility borders only appear for keyboard navigators, keeping mouse interactions clean.
## 2026-07-02 - Accessible Selection Groups
**Learning:** When rendering custom selection groups (like category pickers), buttons need `role="group"`, an `aria-labelledby` association, and `aria-pressed` states to correctly communicate functionality and state to screen readers.
**Action:** Always wrap custom button-based selectors in a `role="group"` container linked to a descriptive label, and use `aria-pressed` on individual options.
## 2025-02-24 - Accessible Custom Toggle Switches
**Learning:** Custom UI toggle switches (often built with `<button>`) frequently lack semantic roles and state indicators, making them invisible or confusing to screen readers, especially when the surrounding text only acts as a visual label.
**Action:** Always add `role="switch"` and dynamically set `aria-checked={state}` on custom toggle buttons. Bind them to adjacent text labels using `aria-labelledby` and `aria-describedby` with matching IDs to ensure complete context is announced to assistive technologies.
## 2025-07-04 - Form Input Accessibility
**Learning:** Form inputs within modal dialogs often miss explicit `aria-label` or `id`/`htmlFor` pairings, relying instead on visual context or placeholder text, which negatively impacts screen reader users.
**Action:** When adding or reviewing modals with form elements, ensure every `<input>` has an explicit `aria-label` and every `<textarea>` is correctly linked to its `<label>` via `id` and `htmlFor`.

## 2024-05-28 - Screen Reader Compatibility for Collapsible Sidebars
**Learning:** Conditionally unmounting DOM text elements (e.g., `{isOpen && <span>Label</span>}`) for visual collapsing completely removes the accessible name from buttons and links for screen reader users.
**Action:** When hiding text to leave only icons in a collapsed state, apply the `sr-only` class to keep the text semantically available in the DOM rather than removing the node entirely.

## 2024-05-28 - Hiding Redundant Tooltip Announcements
**Learning:** If a navigation link or button contains `sr-only` text, and it also triggers a hover tooltip component displaying the identical text, screen readers will read the label twice (once from the DOM element, once from the tooltip structure).
**Action:** Always add `aria-hidden="true"` to visual-only hover tooltips that duplicate the accessible text already present inside the parent interactive element.

## 2024-07-12 - Form Accessibility Improvement
**Learning:** Found multiple form inputs (`<input>`, `<select>`) on the Settings page that had visual `<label>` elements but lacked the programmatic `htmlFor` and `id` linkage, making them inaccessible to screen readers and unclickable for focusing.
**Action:** Always ensure any `<label>` used in a form context is strictly bound to its corresponding input field via `htmlFor="some-id"` and `id="some-id"` to comply with a11y standards.
## 2024-07-14 - Semantic Interactive Table Headers
**Learning:** Table header cells (`<th>`) acting as sort toggles lack native keyboard support and semantic meaning when bound directly with `onClick` and plain text arrows.
**Action:** Always wrap interactive header content in `<button type="button">`, include `aria-label`s, apply `focus-visible:ring-2` styling, and use semantic SVGs for directional feedback instead of raw text like "▲" and "▼".
## 2026-07-20 - Search Input Clear Button UX

**Learning:** When users click a custom "Clear Search" button ('X' icon) to reset a search input, their focus typically drops to the button or body, interrupting the flow of keyboard navigation.
**Action:** Always ensure that clicking a clear button not only resets the query state but also programmatically returns focus to the input (`element.focus()`) to maintain seamless keyboard navigation flow.
