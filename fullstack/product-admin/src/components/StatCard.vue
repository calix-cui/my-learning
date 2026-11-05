<script setup lang="ts">
withDefaults(
  defineProps<{
    label: string
    value: number | string
    hint?: string
    tone?: 'default' | 'primary' | 'success' | 'warning'
  }>(),
  { hint: '', tone: 'default' },
)
</script>

<template>
  <article class="stat-card">
    <div class="stat-card__main">
      <span class="stat-card__label">{{ label }}</span>
      <strong class="stat-card__value" :class="{ 'stat-card__value--primary': tone === 'primary' }">
        {{ value }}
      </strong>
      <span v-if="hint" class="stat-card__hint" :title="hint">{{ hint }}</span>
    </div>
    <div class="stat-card__icon" :class="`stat-card__icon--${tone}`">
      <slot />
    </div>
  </article>
</template>
