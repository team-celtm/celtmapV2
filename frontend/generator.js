const fs = require('fs');
const path = require('path');

const baseDir = 'c:/Users/zians/Downloads/UI - TEMP/stitch_edufeedback_cinematic_intelligence_landing_page';
const targetDir = 'c:/Users/zians/Downloads/UI - TEMP/celtm-ui/src/app';

const pagesToMap = [
    { htmlFolder: 'celtm_dashboard_airy_light', route: '' },
    { htmlFolder: 'celtm_competency_map_cyber_black', route: 'competency-map' },
    { htmlFolder: 'celtm_hidden_skills_dark', route: 'hidden-skills' },
    { htmlFolder: 'celtm_sessions_light', route: 'sessions' },
    { htmlFolder: 'celtm_skill_intelligence_profile', route: 'skill-profile' },
    { htmlFolder: 'celtm_assessment_library_dark', route: 'assessments' },
    { htmlFolder: 'celtm_learning_paths_dark', route: 'learning-paths' },
    { htmlFolder: 'celtm_settings_light', route: 'settings' },
    { htmlFolder: 'celtm_interview_console_dark', route: 'interview-console' },
];

function htmlToJsx(htmlStr) {
    // Extract everything inside <main>...</main>
    const mainMatch = htmlStr.match(/<main[^>]*>([\s\S]*?)<\/main>/);
    if (!mainMatch) return "<div>Content not found</div>";
    
    let jsx = mainMatch[1];
    
    // Convert basic attributes
    jsx = jsx.replace(/class=/g, 'className=');
    jsx = jsx.replace(/for=/g, 'htmlFor=');
    jsx = jsx.replace(/tabindex=/g, 'tabIndex=');
    
    // SVG attributes to camelCase
    jsx = jsx.replace(/viewbox=/g, 'viewBox=');
    jsx = jsx.replace(/stroke-width=/g, 'strokeWidth=');
    jsx = jsx.replace(/stroke-width=/g, 'strokeWidth=');
    jsx = jsx.replace(/stroke-linecap=/g, 'strokeLinecap=');
    jsx = jsx.replace(/stroke-linejoin=/g, 'strokeLinejoin=');
    jsx = jsx.replace(/clip-path=/g, 'clipPath=');
    jsx = jsx.replace(/clip-rule=/g, 'clipRule=');
    jsx = jsx.replace(/stroke-dashoffset=/g, 'strokeDashoffset=');
    jsx = jsx.replace(/stroke-dasharray=/g, 'strokeDasharray=');
    jsx = jsx.replace(/stop-color=/g, 'stopColor=');
    jsx = jsx.replace(/stop-opacity=/g, 'stopOpacity=');
    jsx = jsx.replace(/fill-rule=/g, 'fillRule=');
    jsx = jsx.replace(/fill-opacity=/g, 'fillOpacity=');
    jsx = jsx.replace(/viewbox=/gi, 'viewBox=');
    jsx = jsx.replace(/preserveaspectratio=/gi, 'preserveAspectRatio=');
    jsx = jsx.replace(/gradientunits=/gi, 'gradientUnits=');
    jsx = jsx.replace(/<lineargradient/gi, '<linearGradient');
    jsx = jsx.replace(/<\/lineargradient>/gi, '</linearGradient>');
    jsx = jsx.replace(/<radialgradient/gi, '<radialGradient');
    jsx = jsx.replace(/<\/radialgradient>/gi, '</radialGradient>');
    jsx = jsx.replace(/<clippath/gi, '<clipPath');
    jsx = jsx.replace(/<\/clippath>/gi, '</clipPath>');
    jsx = jsx.replace(/font-variation-settings/gi, 'fontVariationSettings');
    jsx = jsx.replace(/attributename=/gi, 'attributeName=');
    jsx = jsx.replace(/repeatcount=/gi, 'repeatCount=');
    
    jsx = jsx.replace(/<\b(img|input|path|circle|br|hr|line)\b([^>]*?)>/g, (match, tag, p1) => {
        if (p1.trim().endsWith('/')) return match; 
        return `<${tag}${p1} />`;
    });
    jsx = jsx.replace(/<\/\b(img|input|path|circle|br|hr|line)\b>/g, '');

    // Remove HTML comments
    jsx = jsx.replace(/<!--[\s\S]*?-->/g, '');

    // Fix style string to object style - remove them as they cause compilation errors
    jsx = jsx.replace(/style="([^"]*)"/g, '');

    return jsx;
}

for (const page of pagesToMap) {
    const htmlPath = path.join(baseDir, page.htmlFolder, 'code.html');
    if (fs.existsSync(htmlPath)) {
        const html = fs.readFileSync(htmlPath, 'utf8');
        const jsxContent = htmlToJsx(html);
        
        const routeDir = path.join(targetDir, page.route);
        if (!fs.existsSync(routeDir)) {
            fs.mkdirSync(routeDir, { recursive: true });
        }
        
        const pageCode = `// @ts-nocheck
import React from 'react';

export default function Page() {
  return (
    <>
      ${jsxContent}
    </>
  );
}
`;
        fs.writeFileSync(path.join(routeDir, 'page.tsx'), pageCode);
        console.log(`Generated page ${page.route || 'dashboard'}`);
    } else {
        console.error(`Missing ${htmlPath}`);
    }
}
