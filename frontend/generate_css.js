const fs = require('fs');
const path = require('path');

const baseDir = 'c:/Users/zians/Downloads/UI - TEMP/stitch_edufeedback_cinematic_intelligence_landing_page';
const lightHtml = fs.readFileSync(path.join(baseDir, 'celtm_dashboard_airy_light/code.html'), 'utf8');
const darkHtml = fs.readFileSync(path.join(baseDir, 'celtm_competency_map_cyber_black/code.html'), 'utf8');

function extractColors(html) {
    const match = html.match(/"colors":\s*({[^}]+})/);
    if (match) {
        return JSON.parse(match[1]);
    }
    return {};
}

const lightColors = extractColors(lightHtml);
const darkColors = extractColors(darkHtml);

let globalCss = `
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
`;

for (const [key, value] of Object.entries(lightColors)) {
    globalCss += `    --${key}: ${value};\n`;
}

globalCss += `  }\n\n  .dark {\n`;

for (const [key, value] of Object.entries(darkColors)) {
    globalCss += `    --${key}: ${value};\n`;
}

globalCss += `  }\n}\n`;
globalCss += `
@layer components {
    .glass-card {
        background: rgba(255, 255, 255, 0.6);
        backdrop-filter: blur(25px);
        -webkit-backdrop-filter: blur(25px);
    }
    .dark .glass-card {
        background: rgba(159, 167, 255, 0.1);
    }
    .glow-tail { filter: drop-shadow(0 0 8px rgba(159, 167, 255, 0.6)); }
    .no-scrollbar::-webkit-scrollbar { display: none; }
}

body { font-family: var(--font-manrope), sans-serif; }
.material-symbols-outlined { font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24; }
`;

fs.writeFileSync('c:/Users/zians/Downloads/UI - TEMP/celtm-ui/src/app/globals.css', globalCss);

let tailwindConfig = `
import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
`;

const allKeys = new Set([...Object.keys(lightColors), ...Object.keys(darkColors)]);
for (const key of allKeys) {
    tailwindConfig += `        "${key}": "var(--${key})",\n`;
}

tailwindConfig += `      },
      borderRadius: {
        "DEFAULT": "1rem",
        "lg": "2rem",
        "xl": "3rem",
        "full": "9999px"
      },
    },
  },
  plugins: [],
} satisfies Config;
`;

fs.writeFileSync('c:/Users/zians/Downloads/UI - TEMP/celtm-ui/tailwind.config.ts', tailwindConfig);
console.log("Generated CSS and Tailwind Config successfully.");
