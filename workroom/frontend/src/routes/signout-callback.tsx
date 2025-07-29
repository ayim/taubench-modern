import { Navigate, createFileRoute } from '@tanstack/react-router';

export const Route = createFileRoute('/signout-callback')({
  component: () => {
    return <Navigate to="/" />;
  },
});
