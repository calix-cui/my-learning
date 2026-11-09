// ESLint 10 flat config —— 按 ADR-0002「轻量档」配置
//
// 原则（见 docs/adr/0002-frontend-quality-gate-lite.md）：
// 1. 只开 recommended 级别，不启用需要类型信息的 type-aware 规则（跑得慢、报错多、收益低）。
// 2. 只拦「会出错」的问题，不管风格（风格交给 Prettier，且 Prettier 不进 CI 阻断）。
// 3. 升级触发条件写在 ADR 里：前端 > 8000 行 / 组件 > 40 个 / 同类事故 ≥ 2 次 / E2E > 30 条。
import js from '@eslint/js'
import prettier from 'eslint-config-prettier'
import pluginVue from 'eslint-plugin-vue'
import vueA11y from 'eslint-plugin-vuejs-accessibility'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default [
  { ignores: ['dist/**', 'node_modules/**', '.acceptance/**', 'coverage/**'] },

  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...pluginVue.configs['flat/essential'],
  // 无障碍只开 recommended：拦「读屏器真的读不到」的问题（缺 alt、缺 label、div 当按钮）
  ...vueA11y.configs['flat/recommended'],

  {
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: { ...globals.browser },
    },
  },

  // .vue 里的 <script lang="ts"> 用 TypeScript 解析器
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: { parser: tseslint.parser },
    },
  },

  // Node 侧脚本与配置文件
  {
    files: ['**/*.mjs', 'vite.config.ts', 'scripts/**'],
    languageOptions: { globals: { ...globals.node } },
  },

  {
    rules: {
      // 允许用 _ 前缀表示「有意不用」
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // 视图文件名已是 ProductList.vue / CategoryManage.vue 这类多词名，
      // 但 Element Plus 的用法里偶有单词组件，规则本身对路由视图无收益，关掉
      'vue/multi-word-component-names': 'off',
    },
  },

  // 必须放最后：关掉与 Prettier 冲突的格式类规则
  prettier,
]
