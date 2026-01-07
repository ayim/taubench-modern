import { FC, useMemo } from 'react';
import z from 'zod';
import { Controller, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { IconDatabaseError, IconStatusCompleted } from '@sema4ai/icons';
import { Button, Dialog, Form, Select, useSnackbar } from '@sema4ai/components';
import { trpc, TrpcOutput } from '~/lib/trpc';
import { useUserPermissionsQuery } from '~/queries/userPermissions';

type User = TrpcOutput['userManagement']['getUserDetails'];
type Roles = TrpcOutput['userManagement']['listAvailableRoles']['roles'];

type Role = Roles[number]['id'];

const schema = (roles: Roles) => {
  const roleIds = roles.map((role) => role.id);

  return z.object({
    userId: z.string(),
    role: z.enum(roleIds as [Role, ...Role[]]),
  });
};

type FormSchema = z.infer<ReturnType<typeof schema>>;

interface Props {
  user: User;
  roles: Roles;
  onClose: () => void;
  open: boolean;
}

export const UserRoleDialog: FC<Props> = ({ user, roles, onClose, open }) => {
  const { data: userPermissions, refetch: refetchUserPermissions } = useUserPermissionsQuery({ enabled: false });
  const trpcUtils = trpc.useUtils();

  const { addSnackbar } = useSnackbar();

  const { mutateAsync: onUpdateUserRole } = trpc.userManagement.updateUser.useMutation({
    onError: (error) => {
      addSnackbar({
        message: error.message,
        variant: 'danger',
        icon: IconDatabaseError,
      });
    },
    onSuccess: async (_, data) => {
      trpcUtils.userManagement.getUserDetails.invalidate({ userId: user.id });
      trpcUtils.userManagement.listUsers.invalidate();

      // Invalidate user permission query if user changes own role
      if (userPermissions?.userId === data.userId) {
        await refetchUserPermissions();
      }
      onClose();

      addSnackbar({
        message: 'Successfully updated user role',
        variant: 'success',
        icon: IconStatusCompleted,
      });
    },
  });

  const {
    control,
    handleSubmit,
    formState: { isSubmitting },
  } = useForm<FormSchema>({
    resolver: zodResolver(schema(roles)),
    defaultValues: {
      userId: user.id,
      role: user.role,
    },
  });

  const roleItems = useMemo(() => roles.map((role) => ({ value: role.id, label: role.name })), [roles]);

  const onSubmit = handleSubmit((data) =>
    onUpdateUserRole({
      userId: user.id,
      update: {
        role: data.role,
      },
    }),
  );

  return (
    <Dialog onClose={onClose} open={open}>
      <Dialog.Header>
        <Dialog.Header.Title title="Update User Role" />
      </Dialog.Header>
      <Form onSubmit={onSubmit} busy={isSubmitting}>
        <Dialog.Content>
          <Controller
            name="role"
            control={control}
            render={({ field, fieldState: { error } }) => (
              <Select label="Role" items={roleItems} {...field} error={error?.message} />
            )}
          />
        </Dialog.Content>
        <Dialog.Actions>
          <Button type="submit" disabled={isSubmitting} loading={isSubmitting} round>
            Update
          </Button>
          <Button onClick={onClose} variant="secondary" disabled={isSubmitting} round>
            Cancel
          </Button>
        </Dialog.Actions>
      </Form>
    </Dialog>
  );
};
