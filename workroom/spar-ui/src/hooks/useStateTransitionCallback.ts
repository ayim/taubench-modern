import { useEffect, useRef } from 'react';

/**
 * A hook that runs a callback only once when state transitions from one specific value to another. Eg. when chat tool_call goes from "in progress" to "done"
 * There might be a case when we want to watch multiple states and multiple finished states - feel free to optimize this
 *
 * @example
 * useStateTransitionCallback<'in_progress' | 'done'>({ onTransition: onComplete, from: 'in_progress', to: 'done' }, state);
 */
export const useStateTransitionCallback = <T extends string | boolean | number | undefined | null>(
  { onTransition, from, to }: { onTransition: () => void; from: T; to: T },
  currentState: T,
) => {
  const hasTriggered = useRef(false);
  const previousState = useRef<T>(currentState);

  useEffect(() => {
    const shouldTransition = !hasTriggered.current && previousState.current === from && currentState === to;

    if (shouldTransition) {
      hasTriggered.current = true;
      onTransition();
    }

    if (!hasTriggered.current && !shouldTransition) {
      previousState.current = currentState;
    }
  }, [currentState, from, to]);

  return hasTriggered.current;
};
