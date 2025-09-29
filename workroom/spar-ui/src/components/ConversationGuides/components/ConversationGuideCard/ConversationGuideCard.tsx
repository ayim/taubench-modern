import { FC } from "react"
import { IconArrowUp } from "@sema4ai/icons";
import { Box, Button, Typography } from "@sema4ai/components"
import { styled } from "@sema4ai/theme";

interface ConversationGuideCardProps {
  title: string;
  disabled: boolean;
  onClick?: () => void;
}

const Container = styled(Box)<{ disabled: boolean }>`
  ${({ disabled }) => disabled && `
    opacity: 0.6;
    cursor: not-allowed;
    pointer-events: none;
  `}
`

export const ConversationGuideCard: FC<ConversationGuideCardProps> = ({ title, onClick, disabled }) => {
  return (
    <Container 
      display='flex' 
      flexDirection='row' 
      alignItems='center' 
      justifyContent='space-between' 
      p="$16"
      borderRadius='24px'
      boxShadow="0px 0px 0px 0.5px #0000001A inset, 0px 2px 6px 0px #0000000D, 0px 2px 4px -1px #0000000D"
      disabled={disabled}
    >
      <Typography variant="body-large-loose">&quot;{title}&quot;</Typography>
      <Button
          icon={IconArrowUp}
          aria-label="Send message"
          variant="primary"
          round
          type="submit"
          onClick={onClick}
          disabled={disabled}
        />
    </Container>
  );
}