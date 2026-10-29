// replace_emoji_with_svg.js
// Utility script to replace emoji characters in source files with SVG icon references.
// Usage (from project root):
//   node src/scripts/replace_emoji_with_svg.js
// It scans .js, .html, .css files under the "src" directory.

const fs = require('fs');
const path = require('path');

// Simple mapping from emoji character to SVG filename (place SVGs in src/static/icons/)
const emojiMap = {
  '😀': 'smile.svg',
  '🚀': 'rocket.svg',
  '💡': 'idea.svg',
  // Add more mappings as needed
};

function replaceInFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  let changed = false;
  for (const [emoji, svg] of Object.entries(emojiMap)) {
    const regex = new RegExp(emoji, 'g');
    if (regex.test(content)) {
      const replacement = `<svg class="icon"><use href="/static/icons/${svg}#icon"></use></svg>`;
      content = content.replace(regex, replacement);
      changed = true;
    }
  }
  if (changed) {
    fs.writeFileSync(filePath, content, 'utf8');
    console.log(`Updated ${filePath}`);
  }
}

function walk(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      // Skip node_modules and build output directories
      if (['node_modules', 'dist', 'build', '.git'].includes(entry.name)) continue;
      walk(fullPath);
    } else if (entry.isFile()) {
      if (fullPath.match(/\.(js|jsx|ts|tsx|html|css)$/i)) {
        replaceInFile(fullPath);
      }
    }
  }
}

// Start from the src folder (project root assumed to be the current working directory)
walk(path.resolve(__dirname, '..'));
