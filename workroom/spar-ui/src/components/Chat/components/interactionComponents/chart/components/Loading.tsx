import { IconReportsChart } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';
import { FC } from 'react';

interface LoadingBoxProps {
  width?: string | number;
  height?: string | number;
  className?: string;
}

const StyledLoadingBox = styled.div<LoadingBoxProps>`
  width: ${({ width }) => (typeof width === 'number' ? `${width}px` : width || '100px')};
  height: ${({ height }) => (typeof height === 'number' ? `${height}px` : height || '100px')};
  border-radius: 4px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
`;

const LoadingText = styled.div`
  &::after {
    content: '.';
  }
`;

const LoadingBox: FC<LoadingBoxProps> = ({ width, height, className }) => {
  return (
    <StyledLoadingBox width={width} height={height} className={className}>
      <IconReportsChart size={24} />
      <LoadingText>Loading chart</LoadingText>
    </StyledLoadingBox>
  );
};

export default LoadingBox;
