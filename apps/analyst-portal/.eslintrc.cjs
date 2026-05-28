module.exports = {
  root: true,
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    '../../.eslintrc.cjs',
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: { project: ['./tsconfig.json'], tsconfigRootDir: __dirname },
  plugins: ['@typescript-eslint'],
  env: { browser: true, es2022: true },
  ignorePatterns: ['dist/', 'node_modules/', 'vite.config.ts'],
};
