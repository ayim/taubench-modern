import { useState, useCallback } from 'react';

export const useResizablePanel = () => {
  const [stepperWidth, setStepperWidth] = useState(621);
  const minStepperWidth = 621;
  const maxStepperWidth = 1200;

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startX = e.clientX;
      const startWidth = stepperWidth;

      const handleMouseMove = (event: MouseEvent) => {
        const deltaX = startX - event.clientX; // Reversed for left-side resize
        const newWidth = Math.min(Math.max(startWidth + deltaX, minStepperWidth), maxStepperWidth);
        setStepperWidth(newWidth);
      };

      const handleMouseUp = () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    },
    [stepperWidth],
  );

  return {
    stepperWidth,
    handleMouseDown,
    minStepperWidth,
  };
};
