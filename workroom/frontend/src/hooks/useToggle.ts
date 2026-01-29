import { useCallback, useState } from 'react';

export const useToggle = (initialState?: boolean) => {
  const [val, setVal] = useState(initialState || false);

  /**
   * Toggles or updates the value
   * If `toVal` is provided with boolean value, state is updated to that value
   * If `toVal` is undefined or non-boolean, it toggles the state value
   */
  const toggle = useCallback((toVal?: boolean | unknown) => {
    if (typeof toVal === 'boolean') {
      setVal(toVal);
    } else {
      setVal((v) => !v);
    }
  }, []);

  const setTrue = useCallback(() => {
    setVal(true);
  }, []);
  const setFalse = useCallback(() => {
    setVal(false);
  }, []);

  return { val, setVal, toggle, setTrue, setFalse };
};
