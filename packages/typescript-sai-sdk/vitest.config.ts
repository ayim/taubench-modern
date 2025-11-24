import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Test files pattern
    include: ['tests/**/*.test.ts'],

    // Environment setup
    environment: 'node',

    // Global test configuration
    globals: true,

    // Timeout for tests that might involve network calls
    testTimeout: 55000,

    // Setup files (if needed)
    setupFiles: ['./tests/setup.ts'],

    // Coverage configuration
    coverage: {
      provider: 'v8',
      include: ['src/**/*.ts'],
      exclude: ['src/**/*.test.ts', 'src/**/*.spec.ts', 'src/**/index.ts', 'node_modules/**'],
      reporter: ['text', 'json', 'html'],
    },

    // Reporter configuration
    reporters: ['verbose'],

    // Mock configuration
    clearMocks: true,
    restoreMocks: true,

    // Allow only tests to be run
    allowOnly: true,

    // Use single worker to avoid cleanup issues with tinypool
    pool: 'threads',
    poolOptions: {
      threads: {
        singleThread: true,
      },
    },
  },

  // Resolve configuration for imports
  resolve: {
    alias: {
      '@': './src',
    },
  },
});
