import { Button } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';

export const FavouriteButton = styled(Button)<{ $active?: boolean }>`
  svg {
    fill: ${({ $active, theme }) => ($active ? theme.colors.yellow80.color : 'none')};
    color: ${({ $active, theme }) => ($active ? theme.colors.yellow80.color : 'inherit')};
  }
`;
