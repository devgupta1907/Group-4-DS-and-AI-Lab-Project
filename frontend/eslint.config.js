// The frontend rules from AGENTS.md, made mechanical.
//
// Everything here maps to a numbered rule in that document. If you are about to
// add an eslint-disable, read the rule first — it usually means the code wants
// to move, not that the rule is wrong.

import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import importPlugin from 'eslint-plugin-import';

const NETWORK_MESSAGE =
  'Rule 1: components and hooks never call the network directly. Add the call to ' +
  'features/<feature>/api/ or shared/api/, then consume it through a hook.';

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'eslint.config.js'] },

  {
    files: ['**/*.{ts,tsx}'],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      import: importPlugin,
    },
    settings: {
      'import/resolver': {
        typescript: { project: './tsconfig.app.json' },
        node: { extensions: ['.ts', '.tsx'] },
      },
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],

      // --- Rule 4: no `any`, ever. The profile contract is the whole point. ---
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/consistent-type-imports': [
        'error',
        { prefer: 'type-imports', fixStyle: 'inline-type-imports' },
      ],

      // --- Rule 5: small files, small functions. ---
      'max-lines': ['error', { max: 200, skipBlankLines: true, skipComments: true }],
      'max-lines-per-function': [
        'error',
        { max: 80, skipBlankLines: true, skipComments: true },
      ],
      complexity: ['error', 12],

      // --- Rule 6: feature isolation. ---
      'import/no-restricted-paths': [
        'error',
        {
          zones: [
            {
              target: './src/shared',
              from: './src/features',
              message:
                'Rule 6: shared/ must not know about any feature. Move the shared ' +
                'piece down, or keep it inside the feature.',
            },
            {
              target: './src/shared',
              from: './src/app.tsx',
              message: 'Rule 6: shared/ must not import from the app shell.',
            },
          ],
        },
      ],
      'import/no-cycle': ['error', { maxDepth: 4 }],
      'import/order': [
        'error',
        {
          groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
          pathGroups: [
            { pattern: '@shared/**', group: 'internal' },
            { pattern: '@features/**', group: 'internal' },
          ],
          'newlines-between': 'always',
          alphabetize: { order: 'asc', caseInsensitive: true },
        },
      ],
    },
  },

  // --- Rule 1: only the api/ layers may speak to the network. ---
  {
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/shared/api/**', 'src/features/*/api/**'],
    rules: {
      'no-restricted-globals': [
        'error',
        { name: 'fetch', message: NETWORK_MESSAGE },
        { name: 'XMLHttpRequest', message: NETWORK_MESSAGE },
        { name: 'EventSource', message: NETWORK_MESSAGE },
      ],
      'no-restricted-properties': [
        'error',
        { object: 'window', property: 'fetch', message: NETWORK_MESSAGE },
      ],
    },
  },

  // --- Rule 2: components consume hooks; they do not orchestrate requests. ---
  {
    files: ['src/features/*/components/**/*.tsx', 'src/shared/ui/**/*.tsx'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['**/api/*', '@features/*/api/*', '@shared/api/*'],
              message:
                'Rule 2: a component must not import the api layer. Put the call ' +
                'in a hook and render what the hook returns.',
            },
          ],
        },
      ],
      // Rule 5: components are smaller than hooks, because JSX grows fastest.
      'max-lines': ['error', { max: 150, skipBlankLines: true, skipComments: true }],
    },
  },

  // --- shared/ui is presentational. It gets no app knowledge at all. ---
  {
    files: ['src/shared/ui/**/*.tsx'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@features/*', '**/features/*'],
              message:
                'Rule 6: shared/ui primitives are feature-agnostic. If it needs to ' +
                'know about resumes, it belongs in features/resume-parsing/components.',
            },
          ],
        },
      ],
    },
  },
);
