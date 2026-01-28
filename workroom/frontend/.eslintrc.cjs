module.exports = {
  root: true,
  extends: ['@sema4ai/eslint-config-frontend'],
  settings: {
    'import/resolver': {
      typescript: {},
    },
  },
  rules: {
    'no-shadow': 'off',
    '@typescript-eslint/no-shadow': 'warn',
    '@typescript-eslint/no-use-before-define': 'off',
    'react/function-component-definition': 'off',
    'jsx-a11y/anchor-is-valid': 'off',
    'import/no-extraneous-dependencies': [
      'error',
      { devDependencies: ['**/*.test.ts', '**/*.test.tsx', 'vitest.config.ts'] },
    ],
    'no-use-before-define': [
      'error',
      {
        functions: false,
      },
    ],
  },
};
