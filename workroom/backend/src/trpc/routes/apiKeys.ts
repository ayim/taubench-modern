import { TRPCError } from '@trpc/server';
import z from 'zod';
import { authedProcedure } from '../trpc.js';
import { notAvailableForConfiguration, toTRPCError } from './utils.js';

export const list = authedProcedure(['users.read'])
  .output(
    z.object({
      apiKeys: z.array(
        z.object({
          createdAt: z.string(),
          id: z.string().uuid(),
          lastUsedAt: z.string().nullable(),
          name: z.string(),
          updatedAt: z.string(),
        }),
      ),
    }),
  )
  .query(async ({ ctx }) => {
    const { apiKeysManager } = ctx;

    if (!apiKeysManager) {
      throw new TRPCError(notAvailableForConfiguration({ feature: 'API keys management' }));
    }

    const result = await apiKeysManager.listApiKeys();
    if (!result.success) {
      throw new TRPCError(toTRPCError(result.error));
    }

    return {
      apiKeys: result.data,
    };
  });

export const get = authedProcedure(['users.read'])
  .input(
    z.object({
      id: z.string().uuid(),
    }),
  )
  .output(
    z.object({
      createdAt: z.string(),
      id: z.string().uuid(),
      lastUsedAt: z.string().nullable(),
      name: z.string(),
      updatedAt: z.string(),
    }),
  )
  .query(async ({ ctx, input }) => {
    const { apiKeysManager } = ctx;

    if (!apiKeysManager) {
      throw new TRPCError(notAvailableForConfiguration({ feature: 'API keys management' }));
    }

    const result = await apiKeysManager.getApiKey({ id: input.id });
    if (!result.success) {
      throw new TRPCError(toTRPCError(result.error));
    }

    if (!result.data) {
      throw new TRPCError({
        code: 'NOT_FOUND',
        message: 'API key not found',
      });
    }

    return result.data;
  });

export const preview = authedProcedure(['users.read'])
  .input(
    z.object({
      id: z.string().uuid(),
    }),
  )
  .output(
    z.object({
      id: z.string().uuid(),
      value: z.string(),
    }),
  )
  .mutation(async ({ ctx, input }) => {
    const { apiKeysManager } = ctx;

    if (!apiKeysManager) {
      throw new TRPCError(notAvailableForConfiguration({ feature: 'API keys management' }));
    }

    const result = await apiKeysManager.previewApiKey({ id: input.id });
    if (!result.success) {
      throw new TRPCError(toTRPCError(result.error));
    }

    if (!result.data) {
      throw new TRPCError({
        code: 'NOT_FOUND',
        message: 'API key not found',
      });
    }

    return result.data;
  });

export const create = authedProcedure(['users.write'])
  .input(
    z.object({
      name: z.string().trim().min(1, 'Name is required').max(100, 'Name must be at most 100 characters'),
    }),
  )
  .output(
    z.object({
      createdAt: z.string(),
      id: z.string().uuid(),
      lastUsedAt: z.string().nullable(),
      name: z.string(),
      updatedAt: z.string(),
      value: z.string(),
    }),
  )
  .mutation(async ({ ctx, input }) => {
    const { apiKeysManager, monitoring } = ctx;

    if (!apiKeysManager) {
      throw new TRPCError(notAvailableForConfiguration({ feature: 'API keys management' }));
    }

    monitoring.logger.info('Creating API key', {
      name: input.name,
    });

    const result = await apiKeysManager.createApiKey({ name: input.name });
    if (!result.success) {
      throw new TRPCError(toTRPCError(result.error));
    }

    return result.data;
  });

export const update = authedProcedure(['users.write'])
  .input(
    z.object({
      id: z.string().uuid(),
      name: z.string().trim().min(1, 'Name is required').max(100, 'Name must be at most 100 characters'),
    }),
  )
  .output(
    z.object({
      createdAt: z.string(),
      id: z.string().uuid(),
      lastUsedAt: z.string().nullable(),
      name: z.string(),
      updatedAt: z.string(),
    }),
  )
  .mutation(async ({ ctx, input }) => {
    const { apiKeysManager, monitoring } = ctx;

    if (!apiKeysManager) {
      throw new TRPCError(notAvailableForConfiguration({ feature: 'API keys management' }));
    }

    monitoring.logger.info('Updating API key', {
      apiKeyId: input.id,
    });

    const result = await apiKeysManager.updateApiKey({
      id: input.id,
      name: input.name,
    });

    if (!result.success) {
      throw new TRPCError(toTRPCError(result.error));
    }

    if (!result.data) {
      throw new TRPCError({
        code: 'NOT_FOUND',
        message: 'API key not found',
      });
    }

    return result.data;
  });

export const remove = authedProcedure(['users.write'])
  .input(
    z.object({
      id: z.string().uuid(),
    }),
  )
  .output(
    z.object({
      id: z.string().uuid(),
    }),
  )
  .mutation(async ({ ctx, input }) => {
    const { apiKeysManager, monitoring } = ctx;

    if (!apiKeysManager) {
      throw new TRPCError(notAvailableForConfiguration({ feature: 'API keys management' }));
    }

    monitoring.logger.info('Deleting API key', {
      apiKeyId: input.id,
    });

    const result = await apiKeysManager.deleteApiKey({ id: input.id });
    if (!result.success) {
      throw new TRPCError(toTRPCError(result.error));
    }

    if (!result.data) {
      throw new TRPCError({
        code: 'NOT_FOUND',
        message: 'API key not found',
      });
    }

    return result.data;
  });
