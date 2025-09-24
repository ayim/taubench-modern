import { FC } from "react"
import { IconArrowUp } from "@sema4ai/icons";
import { Box, Button, Typography } from "@sema4ai/components"

interface ConversationGuideCardProps {
  title: string;
  onClick: () => void;
}

export const ConversationGuideCard: FC<ConversationGuideCardProps> = ({ title, onClick }) => {
  return (
    <Box 
      display='flex' 
      flexDirection='row' 
      alignItems='center' 
      justifyContent='space-between' 
      p="$16"
      borderRadius='24px'
      boxShadow="0px 0px 0px 0.5px #0000001A inset, 0px 2px 6px 0px #0000000D, 0px 2px 4px -1px #0000000D"
    >
      <Typography variant="body-large-loose">&quot;{title}&quot;</Typography>
      <Button
          icon={IconArrowUp}
          aria-label="Send message"
          variant="primary"
          round
          type="submit"
          onClick={onClick}
        />
    </Box>
  );
}