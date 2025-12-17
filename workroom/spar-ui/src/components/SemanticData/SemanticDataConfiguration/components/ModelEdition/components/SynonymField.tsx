import { KeyboardEvent, FC, useEffect, useRef, useState } from 'react';
import { Box, Input } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { useFormContext } from 'react-hook-form';
import { IconCloseSmall } from '@sema4ai/icons';

type Props = {
  fieldName: string;
  initialValue?: string[];
};

const TagContainer = styled.div`
  display: flex;
  align-items: center;
  background-color: ${({ theme }) => theme.colors.background.subtle.light.color};
  padding-left: ${({ theme }) => theme.space.$8};
  border-radius: ${({ theme }) => theme.radii.$4};
  font-family: ${({ theme }) => theme.fonts.code};

  > button {
    display: flex;
    align-items: center;
    background: none;
    font-family: ${({ theme }) => theme.fonts.code};

    .icon {
      color: ${({ theme }) => theme.colors.content.subtle.light.color};
    }

    &:hover .icon {
      color: ${({ theme }) => theme.colors.content.primary.color};
    }
  }
`;

const TagInput = styled.input`
  background-color: ${({ theme }) => theme.colors.background.subtle.light.color};
  padding: 0 ${({ theme }) => theme.space.$8};
  border-radius: ${({ theme }) => theme.radii.$4};
  font-family: ${({ theme }) => theme.fonts.code};
`;

type TagProps = {
  value: string;
  onChange: (value?: string) => void;
};

// TODO: This component is a candidate for Design System, once the functionality is finalyzed
const Tag: FC<TagProps> = ({ value, onChange }) => {
  const [isEditting, setIsEditting] = useState(false);
  const [localValue, setLocalValue] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditting]);

  const onTagChange = () => {
    onChange(localValue);
    setIsEditting(false);
  };

  const onTagKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === 'Tab' || e.key === ',') {
      e.preventDefault();
      onTagChange();
    }
  };

  const onTagRemove = () => {
    onChange();
  };

  if (isEditting) {
    return (
      <TagInput
        ref={inputRef}
        aria-label="Synonym"
        type="text"
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onBlur={onTagChange}
        onKeyDown={onTagKeyDown}
      />
    );
  }

  return (
    <TagContainer>
      <button type="button" onClick={() => setIsEditting(true)}>
        {localValue}
      </button>
      <button type="button" onClick={onTagRemove}>
        <IconCloseSmall size={20} />
      </button>
    </TagContainer>
  );
};

export const SynonymField: FC<Props> = ({ fieldName, initialValue }: Props) => {
  const [tags, setTags] = useState(initialValue ?? []);
  const { setValue } = useFormContext();
  const [newSynonym, setNewSynonym] = useState('');

  const onNewSynonym = () => {
    const synonym = newSynonym.trim().toLocaleLowerCase();
    if (synonym && !tags.includes(synonym)) {
      setTags([...tags, synonym]);
      setValue(fieldName, [...tags, synonym]);
    }
    setNewSynonym('');
  };

  const onNewSynonymKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === 'Tab' || e.key === ',') {
      e.preventDefault();
      onNewSynonym();
      (e.target as HTMLInputElement).focus();
    }
  };

  const onTagChange = (tagIndex: number) => (value: string | undefined) => {
    const newTags = value
      ? tags.map((curr, index) => (index === tagIndex ? value : curr))
      : tags.filter((_, index) => index !== tagIndex);

    setTags(newTags);
    setValue(fieldName, newTags);
  };

  return (
    <Box>
      <Box display="flex" gap="$4" flexWrap="wrap" p="$8">
        {tags.map((curr, index) => (
          <Tag key={curr} value={curr} onChange={onTagChange(index)} />
        ))}
      </Box>
      <Input
        aria-label="New Synonym"
        variant="ghost"
        value={newSynonym}
        placeholder="Add a new synonym"
        onChange={(e) => setNewSynonym(e.target.value)}
        onKeyDown={onNewSynonymKeyDown}
        onBlur={onNewSynonym}
      />
    </Box>
  );
};
