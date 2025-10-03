import { useAuth } from '@sema4ai/robocloud-ui-utils';
import { Navigate, createFileRoute } from '@tanstack/react-router';
import { FullScreenLoader } from '~/components/Loaders';

export const Route = createFileRoute('/tenants/$tenantId/signin-callback')({
  component: View,
});

function View() {
  const { targetUrl, isAuthenticated, isLoading } = useAuth();
  const redirect = isAuthenticated ? targetUrl : '/';

  if (isLoading) {
    return <FullScreenLoader />;
  }

  return <Navigate to={redirect} />;
}
