module.exports = {
  root: true,
  extends: ['@sema4ai/eslint-config-frontend'],
  settings: {
    'import/resolver': {
      alias: {
        extensions: ['.js', '.jsx', '.ts', '.tsx'],
      },
    },
  },
  rules: {
    'no-shadow': 'off',
    '@typescript-eslint/no-shadow': 'warn',
  },
};
