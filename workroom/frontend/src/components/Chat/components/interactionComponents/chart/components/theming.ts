import { Config, VisualizationSpec } from 'vega-embed';

const labelColor = '#001E2B'; // Dark Blue
const tickColor = '#5BA497'; // Teal Green
const markColor = '#2E5842'; // Dark Green
const axisLineColor = '#F4F6F9'; // Light Grey for axis lines
const fontFamily = 'DM Sans';

const RANGE_CONFIG = {
  // [color scheme](https://vega.github.io/vega/docs/schemes/) for categorical data.
  category: [
    '#2E5842',
    '#5CC1A9',
    '#CF6F3C',
    '#3E6D5A',
    '#003C51',
    '#E0977A',
    '#9BAA9C',
    '#33505A',
    '#B78572',
    '#89B0A5',
  ],
  // [color scheme](https://vega.github.io/vega/docs/schemes/) for diverging quantitative ramps.
  diverging: [
    '#2e5842',
    '#4f7054',
    '#708867',
    '#93a17d',
    '#b6bb95',
    '#dad5ae',
    '#ffefca',
    '#f7d6a8',
    '#f1bb8b',
    '#eba072',
    '#e58260',
    '#de6255',
    '#de425b',
  ],
  // [color scheme](https://vega.github.io/vega/docs/schemes/) for quantitative heatmaps.
  heatmap: [
    '#F1F2EE',
    '#E3E6DE',
    '#D4D9CD',
    '#C4CCBD',
    '#B4C0AD',
    '#A3B39D',
    '#91A68D',
    '#7E997D',
    '#6D8C6F',
    '#5D7F63',
    '#4D7257',
    '#3E654C',
    '#2E5842',
  ],
  // [color scheme](https://vega.github.io/vega/docs/schemes/) for rank-ordered data.
  ordinal: [
    '#2E5842',
    '#5CC1A9',
    '#CF6F3C',
    '#3E6D5A',
    '#003C51',
    '#E0977A',
    '#9BAA9C',
    '#33505A',
    '#B78572',
    '#89B0A5',
  ],
  // [color scheme](https://vega.github.io/vega/docs/schemes/) for sequential quantitative ramps.
  ramp: ['#c2ecd3', '#aed8bf', '#9bc5ac', '#88b299', '#759f87', '#638d75', '#517b63', '#4c773b', '#3f6952', '#2e5842'],
  // Array of [symbol](https://vega.github.io/vega/docs/marks/symbol/) names or paths for the default shape palette.
  symbol: ['circle', 'square', 'triangle', 'diamond', 'cross', 'star', 'wye'],
};

export const SEMA4AI_VEGA_LITE_THEME = {
  arc: { fill: markColor },
  area: { fill: markColor },

  axis: {
    domainColor: axisLineColor,
    grid: true,
    gridColor: axisLineColor,
    gridWidth: 1,
    labelColor,
    labelFontSize: 12,
    labelFont: fontFamily,
    titleColor: labelColor,
    titleFontSize: 16,
    titleFont: fontFamily,
    tickColor,
    tickSize: 5,
    titlePadding: 10,
    labelPadding: 4,
  },

  axisBand: {
    grid: false,
  },

  background: undefined,

  group: {
    fill: null,
  },

  legend: {
    labelColor,
    labelFontSize: 14,
    labelFont: fontFamily,
    padding: 5,
    symbolSize: 100,
    symbolType: 'circle',
    titleColor: labelColor,
    titleFontSize: 16,
    titleFont: fontFamily,
    titlePadding: 10,
  },

  line: {
    stroke: markColor,
    strokeWidth: 2,
  },

  path: { stroke: markColor, strokeWidth: 1 },
  rect: { fill: markColor },

  range: RANGE_CONFIG,

  point: {
    filled: true,
    shape: 'circle',
    fill: markColor,
  },

  shape: { stroke: markColor },

  bar: {
    binSpacing: 2,
    fill: markColor,
    stroke: null,
  },

  title: {
    anchor: 'middle',
    fontSize: 22,
    fontWeight: 600,
    offset: 20,
    font: fontFamily,
    color: labelColor,
  },
} as Config;

export const SEMA4AI_VEGA_THEME = {
  arc: { fill: markColor },
  area: { fill: markColor },

  axis: {
    domain: true,
    domainColor: axisLineColor,
    domainWidth: 1,
    grid: true,
    gridColor: axisLineColor,
    gridWidth: 1,
    labelColor,
    labelFontSize: 12,
    labelFont: fontFamily,
    titleColor: labelColor,
    titleFontSize: 16,
    titleFont: fontFamily,
    tickColor,
    tickSize: 5,
    titlePadding: 10,
    labelPadding: 4,
  },

  axisBand: {
    grid: false,
  },

  background: undefined,

  group: {
    fill: null,
  },

  legend: {
    labelColor,
    labelFontSize: 14,
    labelFont: fontFamily,
    padding: 5,
    symbolSize: 100,
    symbolType: 'circle',
    titleColor: labelColor,
    titleFontSize: 16,
    titleFont: fontFamily,
    titlePadding: 10,
  },

  line: {
    stroke: markColor,
    strokeWidth: 2,
  },

  path: { stroke: markColor, strokeWidth: 1 },
  rect: { fill: markColor },

  range: RANGE_CONFIG,

  point: {
    filled: true,
    shape: 'circle',
    fill: markColor,
  },

  shape: { stroke: markColor },

  bar: {
    binSpacing: 2,
    fill: markColor,
    stroke: null,
  },

  title: {
    anchor: 'middle',
    fontSize: 22,
    fontWeight: 600,
    offset: 20,
    font: fontFamily,
    color: labelColor,
  },
} as Config;

export const processChartSpecOverrides = (spec: VisualizationSpec) => {
  // We want to inject/override some style info for charts
  const newSpec = { ...spec } as VisualizationSpec & { width?: number; height?: number };
  newSpec.autosize = { type: 'fit', contains: 'padding' };
  newSpec.background = undefined;
  newSpec.padding = { left: 0, right: 0, top: 0, bottom: 0 };

  // If width/height are unset, set them to 600/400 respectively
  // (Some chart types don't have top-level width/height properties, but
  // we will still use the top-level width/height property to set the
  // chart container size)

  newSpec.width = 700;

  if (!newSpec.height) {
    newSpec.height = 400;
  }

  return newSpec;
};
