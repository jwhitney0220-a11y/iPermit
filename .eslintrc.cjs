/**
 * Root ESLint config for the iPermit monorepo (T01-02 / T01-12).
 *
 * This is a TEMPLATE / base config. The TypeScript/React apps under apps/*
 * (apps/web, apps/analyst-portal) are expected to EXTEND this config rather
 * than redefine these rules, e.g.:
 *
 *   // apps/web/.eslintrc.cjs
 *   module.exports = {
 *     root: true,
 *     extends: ['../../.eslintrc.cjs'],
 *     parserOptions: { project: ['./tsconfig.json'] },
 *   };
 *
 * The headline engineering constraint from AGENTS.md "Engineering Standards"
 * — functions under 60 lines — is enforced here for TS/JS to mirror the Python
 * checker at scripts/checks/check_function_length.py. Keep the two limits in
 * lockstep: if one changes, change the other (do not bump either; split the
 * function instead — see docs/engineering-handbook/01-engineering-standards.md §3).
 */
module.exports = {
  // Stop ESLint from walking further up the tree when this is the root config.
  // Apps that extend this set their own `root: true` and point `extends` here.
  root: false,

  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
    ecmaFeatures: { jsx: true },
  },

  env: {
    browser: true,
    es2022: true,
    node: true,
  },

  plugins: ['@typescript-eslint'],

  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
  ],

  rules: {
    // The 60-line function rule — mirrors scripts/checks/check_function_length.py.
    // Count the function body only (skip blank lines and comments) so the
    // semantics match the Python AST checker as closely as ESLint allows.
    'max-lines-per-function': [
      'error',
      { max: 60, skipBlankLines: true, skipComments: true, IIFEs: true },
    ],

    // Readability-over-cleverness backstops aligned with the handbook.
    complexity: ['warn', 12],
    'max-depth': ['warn', 4],
    'no-console': 'warn',
  },

  // Prettier owns formatting; ESLint owns correctness. Do not add formatting
  // rules here — prettier (.prettierrc.json) is the single formatter.
  ignorePatterns: [
    'node_modules/',
    'build/',
    'dist/',
    'coverage/',
    '*.config.js',
    '*.config.cjs',
  ],
};
