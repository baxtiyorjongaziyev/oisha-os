/**
 * Clear a search query and return focus to its input so keyboard users can
 * immediately start a new search.
 *
 * @param {(value: string) => void} setSearchQuery
 * @param {{ focus: () => void } | null} searchInput
 */
export function clearSearchQuery(setSearchQuery, searchInput) {
  setSearchQuery("");
  searchInput?.focus();
}
