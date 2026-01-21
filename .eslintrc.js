module.exports = {
  env: {
    browser: true,
    es2021: true,
    node: true,
    jest: true
  },
  extends: [
    'eslint:recommended',
    'plugin:playwright/playwright-test',
    'plugin:jest/recommended'
  ],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module'
  },
  plugins: [
    'playwright',
    'jest'
  ],
  rules: {
    'no-unused-vars': 'warn',
    'no-console': 'warn',
    'playwright/missing-playwright-await': 'error',
    'playwright/no-page-pause': 'warn',
    'jest/no-disabled-tests': 'warn',
    'jest/no-focused-tests': 'error'
  },
  overrides: [
    {
      files: ['tests/e2e/**/*.js'],
      rules: {
        'no-console': 'off'
      }
    }
  ]
};