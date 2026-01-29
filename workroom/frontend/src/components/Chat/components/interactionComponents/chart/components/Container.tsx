import { ReactNode, useCallback, useRef, useState } from 'react';
import { Box, Button, Menu } from '@sema4ai/components';
import { IconDotsHorizontal } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';

import { Code } from '~/components/code';

const Container = styled(Box)<{ $menuOpen: boolean }>`
  background-color: ${({ theme }) => theme.colors.background.panels.color};
  border: 1px solid ${({ theme }) => theme.colors.border.subtle.color};
  border-radius: ${({ theme }) => theme.radii.$16};
  padding: ${({ theme }) => theme.space.$16};
  position: relative;

  canvas {
    width: 100% !important;
    height: auto !important;
  }
`;

const ChartTriggerMenu = styled(Button)`
  position: absolute;
  top: ${({ theme }) => theme.space.$8};
  right: ${({ theme }) => theme.space.$8};
`;

interface ChartProps {
  children: ReactNode;
  handleExport: (format: 'svg' | 'png') => Promise<void>;
  /**
   * Parsed spec object
   */
  spec: unknown;
  showSource: boolean;
  onToggleShowSource: () => void;
}

export const ChartContainer = ({ children, handleExport, spec, showSource, onToggleShowSource }: ChartProps) => {
  const chartRef = useRef<HTMLDivElement>(null);
  const charContextMenuBtnRef = useRef<HTMLButtonElement>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  const handlePNGExport = useCallback(() => {
    handleExport('png');
  }, [handleExport]);

  const handleSVGExport = useCallback(() => {
    handleExport('svg');
  }, [handleExport]);

  return (
    <Container $menuOpen={menuOpen} ref={chartRef}>
      {showSource && <Code maxRows={16} value={JSON.stringify(spec, null, 2)} lang="json" />}
      <Box data-testid="chart-canvas-container">{children}</Box>

      <Menu
        trigger={
          <ChartTriggerMenu
            ref={charContextMenuBtnRef}
            aria-label="chart-context-menu"
            variant="ghost"
            icon={IconDotsHorizontal}
            iconSize={32}
            round
          />
        }
        visible={menuOpen}
        setVisible={setMenuOpen}
      >
        <Menu.Item onClick={handleSVGExport}>Save as SVG</Menu.Item>
        <Menu.Item onClick={handlePNGExport}>Save as PNG</Menu.Item>
        <Menu.Item onClick={onToggleShowSource}>{showSource ? 'Show Chart' : 'Show Source'}</Menu.Item>
      </Menu>
    </Container>
  );
};
