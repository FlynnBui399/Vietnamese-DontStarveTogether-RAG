export default [
  {
    files: ["src/**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: {
        CSS: "readonly",
        Element: "readonly",
        fetch: "readonly",
        FormData: "readonly",
        HTMLFormElement: "readonly",
        HTMLTextAreaElement: "readonly",
        HTMLElement: "readonly",
        URL: "readonly",
        document: "readonly",
        window: "readonly",
      },
    },
    rules: {
      eqeqeq: "error",
      "no-constant-binary-expression": "error",
      "no-dupe-keys": "error",
      "no-undef": "error",
      "no-unreachable": "error",
      "no-unused-vars": ["error", { "argsIgnorePattern": "^_" }],
    },
  },
];
