import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      'no-restricted-imports': ['error', {
        patterns: [{
          group: ['@/generated/api', '@/generated/api/*'],
          message:
            'Components must import domain types from features/<x>, never DTOs directly. ' +
            'Only features/*/api.ts and features/*/mappers.ts may import from @/generated/api.',
        }],
      }],
    },
  },
  // Allow the DTO import inside the mapper / fetch boundary files.
  {
    files: [
      'src/features/*/api.ts',
      'src/features/*/mappers.ts',
    ],
    rules: {
      'no-restricted-imports': 'off',
    },
  },
  // TEMPORARY: allow unmigrated features to keep using DTOs until their own
  // migration chunks land. Navigator = Chunk B2, evaluations = Chunk B3.
  // Delete these overrides after B2 / B3 complete.
  {
    files: [
      'src/features/navigator/**/*.{ts,tsx}',
      'src/features/evaluations/**/*.{ts,tsx}',
    ],
    rules: {
      'no-restricted-imports': 'off',
    },
  },
])
