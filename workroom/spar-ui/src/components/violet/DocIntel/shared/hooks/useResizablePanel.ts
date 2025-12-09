import { useState, useCallback } from 'react';

export const useResizablePanel = () => {
  const [panelWidth, setPanelWidth] = useState(621);
  const minPanelWidth = 621;
  const maxPanelWidth = 1200;

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startX = e.clientX;
      const startWidth = panelWidth;

      const handleMouseMove = (event: MouseEvent) => {
        const deltaX = startX - event.clientX; // Reversed for left-side resize
        const newWidth = Math.min(Math.max(startWidth + deltaX, minPanelWidth), maxPanelWidth);
        setPanelWidth(newWidth);
      };

      const handleMouseUp = () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    },
    [panelWidth],
  );

  return {
    panelWidth,
    handleMouseDown,
    minPanelWidth,
  };
};
