/**
 * BCG Base Helpers for PptxGenJS
 * 
 * Import this file at the top of any BCG presentation script.
 * It provides all BCG constants, grid calculations, and reusable slide-building functions.
 * 
 * Usage:
 *   const bcg = require('./path/to/bcg-base.js');
 *   const pres = bcg.createPresentation();
 *   const slide = pres.addSlide();
 *   bcg.addActionTitle(slide, 'Revenue grew 15% YoY');
 *   bcg.addFooter(slide, 1);
 */

const pptxgen = require('pptxgenjs');

// ============================================================
// COLORS (from BCG theme: "The Boston Consulting Group")
// ============================================================
const COLORS = {
  BCG_GREEN:   '29BA74',  // dk2/tx2 - titles, headers, accent
  DARK_GREEN:  '197A56',  // accent2 - chart primary, icon backgrounds
  DEEP_GREEN:  '03522D',  // accent1 - darkest green, sparingly
  DARK_TEXT:   '575757',  // dk1/tx1 - all body text
  LIGHT_BG:    'F2F2F2',  // lt2/bg2 - light gray backgrounds
  WHITE:       'FFFFFF',  // lt1/bg1 - white
  TEAL:        '3EAD92',  // accent4 - secondary accent
  LIME:        'D4DF33',  // accent3 - highlight accent
  MED_GRAY:    '6E6F73',  // accent5 - footnotes, copyright
  NAVY:        '295E7E',  // accent6 - chart accent
  DARK_NAVY:   '2E3558',  // hlink - hyperlinks
  PAGE_NUM:    'B0B0B0',  // page number color
};

// Chart series palette (ordered)
const CHART_COLORS = [
  '197A56', '29BA74', '84E387', 'C2DD79',
  '688910', '00BCD4', '1976D2', '673AB7'
];

// ============================================================
// FONT
// ============================================================
const FONT = 'Trebuchet MS';

// ============================================================
// DIMENSIONS & GRID
// ============================================================
const DIMS = {
  width: 13.33,
  height: 7.50,
  marginLeft: 0.69,
  marginRight: 0.69,
  marginTop: 0.68,
  contentWidth: 11.96,
};

// Title area
const TITLE = {
  x: 0.69,
  y: 0.68,
  w: 11.96,
  h: 0.51,  // 2-line title height
};

// Content area
const CONTENT = {
  x: 0.69,
  yOfficial: 2.28,   // Official live area start (spacious)
  yPractical: 2.10,  // Practical content start (standard - safe below 2-line titles)
  yDense: 1.60,      // Dense content start (minimum safe distance below title)
  yEnd: 6.74,         // Where footnotes begin
  w: 11.96,
};

// Footer positions
const FOOTER = {
  pageNum: { x: 12.21, y: 7.00, w: 0.42, h: 0.17 },
  copyright: { x: 10.38, y: 4.29, w: 5.61, h: 0.11 },
  footnote: { x: 0.69, y: 6.74, w: 9.88, h: 0.45 },
};

// 12-column grid
const GRID_COLS = [0.69, 1.40, 2.42, 3.44, 4.46, 5.49, 6.51, 7.53, 8.55, 9.58, 10.60, 11.62];
const GUTTER = 0.31;

// ============================================================
// GRID HELPERS
// ============================================================

/**
 * Get equal-width column positions for N columns.
 * Returns array of {x, w} objects.
 */
function columns(n) {
  const totalW = CONTENT.w;
  const gutterTotal = (n - 1) * GUTTER;
  const colW = (totalW - gutterTotal) / n;
  const result = [];
  for (let i = 0; i < n; i++) {
    result.push({
      x: CONTENT.x + i * (colW + GUTTER),
      w: colW,
    });
  }
  return result;
}

/**
 * Get content height available for a given density.
 * @param {'hero'|'standard'|'dense'} density
 */
function contentHeight(density = 'standard') {
  const startY = density === 'hero' ? CONTENT.yOfficial 
               : density === 'dense' ? CONTENT.yDense 
               : CONTENT.yPractical;
  return CONTENT.yEnd - startY;
}

/**
 * Get content start Y for a given density.
 */
function contentStartY(density = 'standard') {
  return density === 'hero' ? CONTENT.yOfficial 
       : density === 'dense' ? CONTENT.yDense 
       : CONTENT.yPractical;
}

// ============================================================
// PRESENTATION FACTORY
// ============================================================

/**
 * Create a new presentation pre-configured with BCG dimensions.
 */
function createPresentation(options = {}) {
  const pres = new pptxgen();
  pres.defineLayout({ name: 'BCG_WIDE', width: DIMS.width, height: DIMS.height });
  pres.layout = 'BCG_WIDE';
  pres.author = options.author || 'Boston Consulting Group';
  pres.title = options.title || 'BCG Presentation';
  return pres;
}

// ============================================================
// SLIDE ELEMENT HELPERS
// ============================================================

/**
 * Add a BCG action title to a slide.
 * @param {object} slide - PptxGenJS slide
 * @param {string} text - Action title text (complete sentence)
 * @param {object} opts - Override options
 */
function addActionTitle(slide, text, opts = {}) {
  slide.addText(text, {
    x: TITLE.x,
    y: TITLE.y,
    w: opts.w || TITLE.w,
    h: opts.h || TITLE.h,
    fontSize: opts.fontSize || 24,
    fontFace: FONT,
    color: opts.color || COLORS.BCG_GREEN,
    bold: false,  // BCG titles are explicitly NOT bold
    valign: 'top',
    margin: 0,
    ...opts,
  });
}

/**
 * Add standard BCG footer (page number + copyright).
 * @param {object} slide - PptxGenJS slide
 * @param {number} pageNum - Page number
 * @param {number} year - Copyright year (default: current year)
 */
function addFooter(slide, pageNum, year) {
  const yr = year || new Date().getFullYear();
  
  // Page number
  slide.addText(String(pageNum), {
    x: FOOTER.pageNum.x,
    y: FOOTER.pageNum.y,
    w: FOOTER.pageNum.w,
    h: FOOTER.pageNum.h,
    fontSize: 10,
    fontFace: FONT,
    color: COLORS.PAGE_NUM,
    align: 'center',
  });
  
  // Copyright (rotated)
  slide.addText(`Copyright © ${yr} by Boston Consulting Group. All rights reserved.`, {
    x: FOOTER.copyright.x,
    y: FOOTER.copyright.y,
    w: FOOTER.copyright.w,
    h: FOOTER.copyright.h,
    fontSize: 7,
    fontFace: FONT,
    color: COLORS.MED_GRAY,
    rotate: 270,
  });
}

/**
 * Add a source/footnote line.
 * @param {object} slide
 * @param {string} text - Source text, e.g. "Source: BCG analysis, 2026"
 */
function addSource(slide, text) {
  slide.addText(text, {
    x: FOOTER.footnote.x,
    y: FOOTER.footnote.y,
    w: FOOTER.footnote.w,
    h: FOOTER.footnote.h,
    fontSize: 10,
    fontFace: FONT,
    color: COLORS.MED_GRAY,
    valign: 'top',
    margin: 0,
  });
}

/**
 * Add a section divider slide (green left arrow style).
 * @param {object} pres - PptxGenJS presentation
 * @param {string} title - Section title
 * @param {number} pageNum - Page number
 */
function addSectionDivider(pres, title, pageNum) {
  const slide = pres.addSlide();
  
  // Green arrow shape (left ~1/3)
  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 4.46, h: DIMS.height,
    fill: { color: COLORS.BCG_GREEN },
  });
  
  // Title on green area
  slide.addText(title, {
    x: 0.69, y: 2.93, w: 3.42, h: 1.64,
    fontSize: 32,
    fontFace: FONT,
    color: COLORS.WHITE,
    bold: false,
    valign: 'middle',
  });
  
  addFooter(slide, pageNum);
  return slide;
}

/**
 * Add a numbered badge (green circle with white number).
 */
function addNumberBadge(slide, number, x, y, size = 0.4) {
  slide.addShape(pres.shapes || slide._slideLayout?._presLayout?.shapes?.OVAL, {
    x: x, y: y, w: size, h: size,
    fill: { color: COLORS.BCG_GREEN },
  });
  slide.addText(String(number), {
    x: x, y: y, w: size, h: size,
    fontSize: Math.round(size * 30),
    fontFace: FONT,
    color: COLORS.WHITE,
    bold: true,
    align: 'center',
    valign: 'middle',
  });
}

/**
 * Create a standard content slide with title and footer.
 * Returns the slide for further content additions.
 */
function addContentSlide(pres, title, pageNum, opts = {}) {
  const slide = pres.addSlide();
  
  if (opts.background) {
    slide.background = { color: opts.background };
  }
  
  addActionTitle(slide, title, opts.titleOpts || {});
  addFooter(slide, pageNum);
  
  return slide;
}

// ============================================================
// EXPORTS
// ============================================================

module.exports = {
  // Constants
  COLORS,
  CHART_COLORS,
  FONT,
  DIMS,
  TITLE,
  CONTENT,
  FOOTER,
  GRID_COLS,
  GUTTER,
  
  // Grid helpers
  columns,
  contentHeight,
  contentStartY,
  
  // Presentation factory
  createPresentation,
  
  // Slide element helpers
  addActionTitle,
  addFooter,
  addSource,
  addSectionDivider,
  addNumberBadge,
  addContentSlide,
};
