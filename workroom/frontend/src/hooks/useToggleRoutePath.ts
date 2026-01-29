/* eslint-disable @typescript-eslint/no-explicit-any */
import { useLocation, useRouter } from '@tanstack/react-router';

/**
 * Toggles between target route and default route when already on target path.
 */
export const useToggleRoutePath = (defaultLink: { to: string; params: Record<string, any> }) => {
  const location = useLocation();
  const router = useRouter();

  return (to: string, params: Record<string, any>) => {
    const target = router.buildLocation({ to, params });

    if (location.pathname === target.pathname) {
      return { to: defaultLink.to, params: defaultLink.params };
    }

    return { to, params };
  };
};
