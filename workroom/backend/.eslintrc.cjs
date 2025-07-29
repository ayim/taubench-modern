module.exports = {
  root: true,
  env: { browser: false, es2020: true },
  extends: ['eslint:recommended', 'plugin:@typescript-eslint/recommended'],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parser: '@typescript-eslint/parser',
  plugins: ['import'],
  rules: {
    'no-console': 'error',
    '@typescript-eslint/no-unused-vars': [
      'error',
      {
        vars: 'all',
        args: 'after-used',
        caughtErrors: 'all',
        caughtErrorsIgnorePattern: '^_[a-zA-Z0-9_]*$',
        argsIgnorePattern: '^_[a-zA-Z0-9_]*$',
        destructuredArrayIgnorePattern: '^_[a-zA-Z0-9_]*$',
        varsIgnorePattern: '^_[a-zA-Z0-9_]*$',
        ignoreRestSiblings: true,
      },
    ],
    'import/order': [
      'error',
      {
        groups: ['builtin', 'external', 'internal', ['parent', 'sibling', 'index']],
        'newlines-between': 'never',
        alphabetize: {
          order: 'asc',
          caseInsensitive: true,
        },
      },
    ],
  },
};
