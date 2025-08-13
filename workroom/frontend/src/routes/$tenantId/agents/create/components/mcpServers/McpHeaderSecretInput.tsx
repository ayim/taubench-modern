import { FC, useState, MouseEvent } from 'react';
import { Badge, Select } from '@sema4ai/components';
import { IconCloseSmall, IconEye, IconEyeLock } from '@sema4ai/icons';
import { styled } from '@sema4ai/theme';

type HeaderValueType = { type: 'string'; value: string } | { type: 'secret'; secretID: string };

type Props = {
  headerKey: string;
  headerValue: HeaderValueType;
  items: { label: string; value: string }[];
  onUpdateValue: (key: string, value: string) => void;
  onUpdateSecretId: (key: string, secretId: string) => void;
  onResetToValue: (key: string) => void;
  error?: string;
  disabled?: boolean;
};

const Container = styled.div`
  position: relative;
  > button {
    position: absolute;
    top: 6px;
    left: 5px;
    z-index: 2;
  }
`;

export const McpHeaderSecretInput: FC<Props> = ({
  headerKey,
  headerValue,
  items,
  onUpdateSecretId,
  onUpdateValue,
  onResetToValue,
  error,
  disabled,
}) => {
  const [hideInputValue, setHideInputValue] = useState(true);

  const onToggleVisibility = (e: MouseEvent) => {
    e.preventDefault();
    setHideInputValue(!hideInputValue);
  };

  const secretName =
    headerValue.type === 'secret' ? items.find((curr) => curr.value === headerValue.secretID)?.label : '';

  const SecondaryIcon = hideInputValue ? IconEyeLock : IconEye;

  return (
    <Container>
      {headerValue.type === 'secret' && (
        <Badge
          forwardedAs="button"
          icon={IconEyeLock}
          label={secretName}
          iconAfter={IconCloseSmall}
          iconVisible
          variant="yellow"
          onClick={() => onResetToValue(headerKey)}
          disabled={disabled}
        />
      )}

      <Select
        placeholder={headerValue.type === 'secret' ? '' : `Value for ${headerKey}`}
        type={hideInputValue ? 'secret' : 'text'}
        aria-label="Header value"
        value={headerValue.type === 'string' ? headerValue.value : ''}
        onChange={(value) => onUpdateSecretId(headerKey, value)}
        items={items}
        onInputChange={(e) => onUpdateValue(headerKey, e.target.value)}
        iconRightSecondary={!secretName ? SecondaryIcon : undefined}
        iconRightSecondaryLabel="Toggle input visibility"
        onIconRightSecondaryClick={onToggleVisibility}
        error={error}
        disabled={disabled}
      />
    </Container>
  );
};
