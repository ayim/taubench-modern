import { VisualizationSpec } from 'vega-embed';

const DATA_FRAME_URL_PATTERN = /^data-frame:\/\/(.+)$/;

export const specHasDataFrameUrl = (spec: VisualizationSpec) => {
  const dataUrl = spec.data && 'url' in spec.data ? spec.data.url : null;
  const match = dataUrl ? dataUrl.match(DATA_FRAME_URL_PATTERN) : null;
  if (match) {
    return { dataFrameName: match[1] };
  }
  return null;
};
