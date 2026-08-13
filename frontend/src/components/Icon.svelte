<script>
  export let name;
  export let size = 20;
</script>

<svg
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.8"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  {#if name === 'upload'}
    <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" />
    <path d="M5 14v4.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V14" />
  {:else if name === 'file'}
    <path d="M6.5 3.5h7l4 4v13h-11z" />
    <path d="M13.5 3.5v4h4" />
  {:else if name === 'close'}
    <path d="m7 7 10 10M17 7 7 17" />
  {:else if name === 'download'}
    <path d="M12 4v11m0 0 4-4m-4 4-4-4" />
    <path d="M5 19.5h14" />
  {:else if name === 'check'}
    <path d="m5 12 4.2 4.2L19 6.5" />
  {:else if name === 'retry'}
    <path d="M19 8V4m0 0h-4m4 0-3.1 3.1a7 7 0 1 0 1.2 8.4" />
  {:else if name === 'lock'}
    <rect x="5" y="10" width="14" height="10" rx="2" />
    <path d="M8.5 10V7.5a3.5 3.5 0 0 1 7 0V10" />
  {:else if name === 'play'}
    <path d="m8.5 5.5 10 6.5-10 6.5z" />
  {:else if name === 'pause'}
    <path d="M9 6v12M15 6v12" />
  {:else if name === 'audio'}
    <path d="M5 14v-4M9 17V7M13 14.5v-5M17 18V6M21 13v-2" />
  {:else if name === 'video'}
    <rect x="3.5" y="6" width="13" height="12" rx="2" />
    <path d="m16.5 10 4-2v8l-4-2" />
  {:else if name === 'sun'}
    <circle cx="12" cy="12" r="3.5" />
    <path d="M12 2.5v2M12 19.5v2M21.5 12h-2M4.5 12h-2M18.7 5.3l-1.4 1.4M6.7 17.3l-1.4 1.4M18.7 18.7l-1.4-1.4M6.7 6.7 5.3 5.3" />
  {:else if name === 'moon'}
    <path d="M20 15.2A8.4 8.4 0 0 1 8.8 4a8.4 8.4 0 1 0 11.2 11.2Z" />
  {/if}
</svg>
