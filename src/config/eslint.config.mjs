import js from "@eslint/js";
import tseslint from "typescript-eslint";

const JS_FILES = ["**/*.js", "**/*.jsx"];
const TS_FILES = ["**/*.ts", "**/*.tsx"];

// Broad globals reduce offline false positives for single-file linting.
// This is still a compromise: without the original repo config/runtime, no
// single global set will be perfect for every file.
const COMMON_GLOBALS = {
    // Browser
    console: "readonly", document: "readonly", window: "readonly",
    fetch: "readonly", navigator: "readonly",
    localStorage: "readonly", sessionStorage: "readonly",
    setTimeout: "readonly", setInterval: "readonly",
    clearTimeout: "readonly", clearInterval: "readonly",
    URL: "readonly", URLSearchParams: "readonly",
    FormData: "readonly", Event: "readonly", CustomEvent: "readonly",
    HTMLElement: "readonly", MutationObserver: "readonly",
    IntersectionObserver: "readonly", ResizeObserver: "readonly",
    AbortController: "readonly", Response: "readonly", Request: "readonly",
    Headers: "readonly", Blob: "readonly", File: "readonly", FileReader: "readonly",
    Worker: "readonly", WebSocket: "readonly", EventSource: "readonly",
    crypto: "readonly", performance: "readonly", atob: "readonly", btoa: "readonly",
    requestAnimationFrame: "readonly", cancelAnimationFrame: "readonly",
    queueMicrotask: "readonly", structuredClone: "readonly",
    globalThis: "readonly", Intl: "readonly",
    Map: "readonly", Set: "readonly", WeakMap: "readonly", WeakSet: "readonly",
    Promise: "readonly", Proxy: "readonly", Reflect: "readonly", Symbol: "readonly",
    ArrayBuffer: "readonly", DataView: "readonly",
    Uint8Array: "readonly", Int8Array: "readonly", Int16Array: "readonly",
    Int32Array: "readonly", Uint16Array: "readonly", Uint32Array: "readonly",
    Float32Array: "readonly", Float64Array: "readonly",
    BigInt: "readonly", BigInt64Array: "readonly", BigUint64Array: "readonly",
    TextEncoder: "readonly", TextDecoder: "readonly",
    // DOM types & events
    Element: "readonly", HTMLElement: "readonly",
    HTMLDivElement: "readonly", HTMLInputElement: "readonly", HTMLImageElement: "readonly",
    HTMLButtonElement: "readonly", HTMLFormElement: "readonly", HTMLAnchorElement: "readonly",
    HTMLCanvasElement: "readonly", HTMLSelectElement: "readonly", HTMLTextAreaElement: "readonly",
    SVGElement: "readonly", NodeFilter: "readonly", DocumentFragment: "readonly",
    Range: "readonly", Selection: "readonly", TreeWalker: "readonly",
    MouseEvent: "readonly", KeyboardEvent: "readonly", PointerEvent: "readonly",
    DragEvent: "readonly", FocusEvent: "readonly", ClipboardEvent: "readonly",
    MessageEvent: "readonly", InputEvent: "readonly", TouchEvent: "readonly",
    WheelEvent: "readonly", AnimationEvent: "readonly", TransitionEvent: "readonly",
    // Web APIs
    alert: "readonly", confirm: "readonly", prompt: "readonly",
    location: "readonly", history: "readonly",
    MediaSource: "readonly", ReadableStream: "readonly", WritableStream: "readonly",
    TransformStream: "readonly", CompressionStream: "readonly",
    SharedWorker: "readonly", ServiceWorker: "readonly", Notification: "readonly",
    requestIdleCallback: "readonly", postMessage: "readonly",
    // Common libraries/runtimes
    React: "readonly", ReactDOM: "readonly",
    jQuery: "readonly", $: "readonly",
    chrome: "readonly", Deno: "readonly",
    define: "readonly",  // AMD
    // Node
    require: "readonly", module: "readonly", exports: "readonly",
    __dirname: "readonly", __filename: "readonly",
    process: "readonly", Buffer: "readonly", global: "readonly",
    assert: "readonly",
    // Test
    describe: "readonly", it: "readonly", test: "readonly",
    expect: "readonly", beforeEach: "readonly", afterEach: "readonly",
    beforeAll: "readonly", afterAll: "readonly", jest: "readonly",
    vi: "readonly", cy: "readonly", Cypress: "readonly",
};

const TS_UNUSED_VARS_RULE = ["warn", {
    vars: "all",
    args: "after-used",
    caughtErrors: "none",
    ignoreRestSiblings: true,
    argsIgnorePattern: "^_",
    varsIgnorePattern: "^_",
}];

const TS_ALL_CONFIGS = tseslint.configs.all.map((config) => ({
    ...config,
    files: config.files || TS_FILES,
}));

export default [
    // Maximum built-in JS rule coverage.
    {
        ...js.configs.all,
        files: JS_FILES,
        languageOptions: {
            ...(js.configs.all.languageOptions || {}),
            ecmaVersion: "latest",
            sourceType: "module",
            globals: COMMON_GLOBALS,
        },
    },

    // Maximum TS/TSX rule coverage that can parse in single-file mode.
    ...TS_ALL_CONFIGS,

    // Add globals and parser options for offline single-file analysis.
    {
        files: TS_FILES,
        languageOptions: {
            parser: tseslint.parser,
            parserOptions: {
                ecmaVersion: "latest",
                sourceType: "module",
            },
            globals: COMMON_GLOBALS,
        },
    },

    // Disable rules that require full type information, which this pipeline
    // does not have when linting isolated files in temp directories.
    {
        ...tseslint.configs.disableTypeChecked,
        files: TS_FILES,
        rules: {
            ...(tseslint.configs.disableTypeChecked.rules || {}),
            // Keep undefined-name detection enabled in TS even without a full
            // compiler pass; ESLint still catches real value-space misses.
            "no-undef": "error",
            "no-unused-vars": "off",
            "@typescript-eslint/no-unused-vars": TS_UNUSED_VARS_RULE,
        },
    },
];
