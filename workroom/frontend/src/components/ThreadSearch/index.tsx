import { useEffect, useRef, useState } from 'react';
import { Button, Input, SideNavigation, Tooltip, Typography } from '@sema4ai/components';
import { styled } from '@sema4ai/theme';
import { IconSearch, IconCloseSmall, IconChevronUp, IconChevronDown } from '@sema4ai/icons';
import { useParams } from '@tanstack/react-router';

import { useThreadMessagesQuery } from '~/queries/threads';
import { useThreadSearchStore } from '~/hooks/useThreadSearchStore';

const Container = styled.div<{ $open: boolean }>`
  position: relative;

  ${({ theme }) => theme.screen.s} {
    position: ${({ $open }) => ($open ? 'absolute' : 'relative')};
    right: ${({ $open, theme }) => ($open ? theme.space.$16 : '0')};
    width: ${({ $open }) => ($open ? 'calc(100% - 32px)' : 'auto')};
    z-index: ${({ theme }) => theme.zIndex.dropdown};
  }
`;

const ResultControls = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  position: absolute;
  height: ${({ theme }) => theme.space.$36};
  right: ${({ theme }) => theme.space.$36};
  top: 0;
  z-index: 2;
`;

const SearchInput = styled(Input)`
  padding-right: 128px;
  width: 240px;

  ${({ theme }) => theme.screen.s} {
    width: 100%;
  }
`;

export const ThreadSearch = () => {
  const { threadId = '' } = useParams({ strict: false });
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { data: messages } = useThreadMessagesQuery({ threadId });
  const [searchResults, setSearchResults] = useState<number[]>([]);
  const { query, setQuery, setCurrentMessageIndex, currentMessageIndex } = useThreadSearchStore();

  useEffect(() => {
    if (isSearchOpen) {
      inputRef.current?.focus();
    }
  }, [isSearchOpen]);

  useEffect(() => {
    if (query.length < 3) {
      return;
    }
    // TODO-V2: Improve search logic
    const results =
      messages?.reduce<number[]>((acc, thread, messageIndex) => {
        const contains = thread.content.some((message) => {
          if (message.kind === 'text') {
            return message.text.toLowerCase().includes(query.toLowerCase());
          }

          return false;
        });

        if (contains) {
          return [...acc, messageIndex];
        }
        return acc;
      }, []) || [];

    setSearchResults(results);

    if (results.length > 0) {
      setCurrentMessageIndex(results[0]);
    }
  }, [messages, query]);

  const onToggleSearch = () => {
    setIsSearchOpen((curr) => !curr);
  };

  const onInputBlur = () => {
    if (query.length === 0) {
      setIsSearchOpen(false);
    }
  };

  const onPreviousResult = () => {
    const currentIndex = searchResults.findIndex((result) => result === currentMessageIndex);
    if (currentIndex <= 0) {
      return;
    }
    setCurrentMessageIndex(searchResults[currentIndex - 1]);
  };

  const onNextResult = () => {
    const currentIndex = searchResults.findIndex((result) => result === currentMessageIndex);
    if (currentIndex < 0 || currentIndex === searchResults.length - 1) {
      return;
    }
    setCurrentMessageIndex(searchResults[currentIndex + 1]);
  };

  const onClearSearch = () => {
    setQuery('');
    setIsSearchOpen(false);
    setCurrentMessageIndex(null);
    setSearchResults([]);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      onNextResult();
    }
    if (e.key === 'ArrowUp') {
      onPreviousResult();
    }
    if (e.key === 'ArrowDown') {
      onNextResult();
    }
    if (e.key === 'Escape') {
      onClearSearch();
    }
  };

  useEffect(() => {
    const handleInterceptSearch = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'f') {
        event.preventDefault();
        setIsSearchOpen(true);
      }
    };
    document.addEventListener('keydown', handleInterceptSearch);

    return () => {
      document.removeEventListener('keydown', handleInterceptSearch);
    };
  }, []);

  return (
    <Container $open={isSearchOpen}>
      {!isSearchOpen && (
        <Tooltip text="Search" placement="bottom">
          <SideNavigation.Item icon={IconSearch} round aria-label="Search" onClick={onToggleSearch} />
        </Tooltip>
      )}
      {searchResults.length > 0 && isSearchOpen && (
        <ResultControls>
          <Typography variant="body-small" color="content.subtle.light">
            {searchResults.findIndex((result) => result === currentMessageIndex) + 1}/{searchResults.length}
          </Typography>
          <Button
            aria-label="Previous result"
            size="small"
            variant="ghost-subtle"
            icon={IconChevronUp}
            onClick={onPreviousResult}
          />
          <Button
            aria-label="Next result"
            size="small"
            variant="ghost-subtle"
            icon={IconChevronDown}
            onClick={onNextResult}
          />
        </ResultControls>
      )}
      {isSearchOpen && (
        <SearchInput
          placeholder="Search"
          iconLeft={IconSearch}
          aria-label="Search"
          onBlur={onInputBlur}
          value={query}
          ref={inputRef}
          round
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={onKeyDown}
          iconRight={query.length ? IconCloseSmall : undefined}
          iconRightLabel="Clear search"
          onIconRightClick={onClearSearch}
        />
      )}
    </Container>
  );
};
