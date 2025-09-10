import { ReactNode, useCallback, useRef, useState } from 'react';
import { Box, Button, Menu } from '@sema4ai/components';
import { IconDotsHorizontalCircle } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';

import { Code } from '../../../../../../common/code';

const Container = styled(Box)<{ $menuOpen: boolean }>`
  position: relative;
  width: 100%;

  &:before {
    content: '';
    position: absolute;
    top: 0;
    left: -40px;
    width: 40px;
    height: 100%;
  }

  > button {
    display: ${({ $menuOpen }) => ($menuOpen ? 'block' : 'none')};
  }

  &:hover {
    > button {
      display: block;
    }
  }

  ${({ theme }) => theme.screen.m} {
    &:before {
      display: none;
    }

    canvas {
      width: 100% !important;
      height: auto !important;
    }
  }
`;

const ChartTriggerMenu = styled(Button)`
  position: absolute;
  top: 0;
  left: -${({ theme }) => theme.space.$40};
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
            variant="ghost-subtle"
            icon={IconDotsHorizontalCircle}
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
