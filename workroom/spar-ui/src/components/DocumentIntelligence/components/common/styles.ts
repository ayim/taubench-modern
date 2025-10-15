import { Button } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';

export const StyledEditButton = styled(Button)`
  div {
    width: 64px !important;
  }
`;

export const StyledDeleteButton = styled(Button)`
  div {
    width: 32px !important;
  }
`;


export const StyledAddButton = styled(Button)`
  div {
    width: 80px !important;
  }
`;


export const StyledWidthButton = styled(Button)<{ $width?: string }>`
  div {
    width: ${props => props.$width || 'auto'} !important;
  }
`;


export { Button };
