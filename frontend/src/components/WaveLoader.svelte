<script>
  export let size = 30;
  export let contrast = false;
</script>

<span class="wave-loader" class:contrast style={`--wave-loader-width: ${size}px`} aria-hidden="true">
  <svg viewBox="0 0 36 14" focusable="false">
    <path
      class="wave-loader-back"
      d="M-18 8 C-15 4 -12 4 -9 8 S-3 12 0 8 S6 4 9 8 S15 12 18 8 S24 4 27 8 S33 12 36 8 S42 4 45 8 S51 12 54 8"
    />
    <path
      class="wave-loader-front"
      d="M-18 6 C-15 1.5 -12 1.5 -9 6 S-3 10.5 0 6 S6 1.5 9 6 S15 10.5 18 6 S24 1.5 27 6 S33 10.5 36 6 S42 1.5 45 6 S51 10.5 54 6"
    />
  </svg>
</span>

<style>
  .wave-loader {
    width: var(--wave-loader-width);
    height: calc(var(--wave-loader-width) * .39);
    display: inline-flex;
    flex: 0 0 auto;
    overflow: hidden;
    color: var(--accent);
  }

  .wave-loader.contrast { color: var(--accent-contrast); }

  svg {
    width: 100%;
    height: 100%;
    display: block;
    overflow: hidden;
  }

  path {
    fill: none;
    stroke: currentColor;
    stroke-linecap: round;
    stroke-width: 1.65;
    vector-effect: non-scaling-stroke;
    transform-box: fill-box;
    transform-origin: center;
  }

  .wave-loader-back {
    opacity: .25;
    animation: wave-drift-back 1.6s cubic-bezier(.45, 0, .55, 1) infinite;
  }

  .wave-loader-front {
    animation: wave-drift-front 1.2s cubic-bezier(.45, 0, .55, 1) infinite;
  }

  @keyframes wave-drift-front {
    0% { transform: translate3d(-9px, 1px, 0) scaleY(.82); }
    50% { transform: translate3d(0, -1px, 0) scaleY(1); }
    100% { transform: translate3d(9px, 1px, 0) scaleY(.82); }
  }

  @keyframes wave-drift-back {
    0% { transform: translate3d(9px, 0, 0) scaleY(.9); }
    50% { transform: translate3d(0, 1px, 0) scaleY(.72); }
    100% { transform: translate3d(-9px, 0, 0) scaleY(.9); }
  }

  @media (prefers-reduced-motion: reduce) {
    path { animation: none; }
    .wave-loader-front { transform: translate3d(0, -1px, 0); }
  }
</style>
