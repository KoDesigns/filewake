<script>
  import { onMount } from 'svelte';

  let canvas;

  onMount(() => {
    const context = canvas.getContext('2d', { alpha: false });
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const coarsePointer = window.matchMedia('(pointer: coarse)').matches;
    const pointer = { x: 0, y: 0, targetX: 0, targetY: 0, strength: 0, targetStrength: 0 };
    const ripples = [];
    const rippleDuration = 1600;
    const uiBlockers = 'button, input, select, a, dialog, .service-error, .file-row, .bulk-bar, footer';
    let width = 0;
    let height = 0;
    let animationFrame = 0;
    let lastFrame = 0;
    let visible = !document.hidden;
    let waterColor = '#ffffff';
    let lineColor = '#005bd0';
    let brightLineColor = '#69dbf9';

    function readColors() {
      const styles = getComputedStyle(document.documentElement);
      waterColor = styles.getPropertyValue('--wave-water').trim() || '#ffffff';
      lineColor = styles.getPropertyValue('--wave-line').trim() || '#005bd0';
      brightLineColor = styles.getPropertyValue('--wave-line-bright').trim() || '#69dbf9';
    }

    function resize() {
      width = window.innerWidth;
      height = window.innerHeight;
      const ratio = Math.min(window.devicePixelRatio || 1, coarsePointer ? 1.25 : 1.5);
      canvas.width = Math.max(1, Math.floor(width * ratio));
      canvas.height = Math.max(1, Math.floor(height * ratio));
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      pointer.x ||= width * 0.68;
      pointer.y ||= height * 0.42;
      pointer.targetX ||= pointer.x;
      pointer.targetY ||= pointer.y;
      readColors();
      draw(0);
    }

    function surfaceY(x, baseY, row, time) {
      const phase = time * 0.00018;
      const broad = Math.sin(x * 0.0042 + row * 0.19 + phase) * 13;
      const cross = Math.sin(x * 0.009 - row * 0.115 - phase * 0.72) * 6;
      const swell = Math.sin(x * 0.0019 + row * 0.285 + phase * 0.38) * 25;
      const diagonal = Math.sin((x + baseY * 0.64) * 0.0034 - phase * 0.55) * 10;

      return baseY + broad + cross + swell + diagonal;
    }

    function pointY(x, baseY, row, time) {
      const phase = time * 0.00018;
      const surface = surfaceY(x, baseY, row, time);

      const dx = x - pointer.x;
      const dy = surface - pointer.y;
      const radius = Math.min(330, Math.max(190, width * 0.22));
      const distance = Math.sqrt(dx * dx + dy * dy);
      const influence = distance < radius ? Math.pow(1 - distance / radius, 2) * pointer.strength : 0;
      const current = influence * (
        Math.sin(dx * 0.022 - phase * 4) * 30
        + Math.sin(dx * 0.008 + row * 0.32) * 17
        + (dy / radius) * 22
      );

      let rippleOffset = 0;
      for (const ripple of ripples) {
        const age = time - ripple.startedAt;
        if (age < 0 || age > rippleDuration) continue;
        const rippleDistance = Math.hypot(x - ripple.x, surface - ripple.y);
        const waveRadius = age * 0.24;
        const distanceFromFront = rippleDistance - waveRadius;
        const envelope = Math.exp(-(distanceFromFront * distanceFromFront) / 1450);
        const decay = 1 - age / rippleDuration;
        rippleOffset += Math.cos(distanceFromFront * 0.16) * envelope * decay * 22;
      }

      return surface + current + rippleOffset;
    }

    function draw(time) {
      context.globalAlpha = 1;
      context.fillStyle = waterColor;
      context.fillRect(0, 0, width, height);

      const spacing = coarsePointer ? 29 : 25;
      const step = coarsePointer ? 14 : 11;
      const rowCount = Math.ceil((height + 220) / spacing);
      const lineGradient = context.createLinearGradient(0, 0, width, height);
      lineGradient.addColorStop(0, lineColor);
      lineGradient.addColorStop(0.55, brightLineColor);
      lineGradient.addColorStop(1, lineColor);
      context.strokeStyle = lineGradient;
      context.lineWidth = 0.75;
      context.lineCap = 'round';
      context.lineJoin = 'round';
      context.shadowBlur = 0;
      context.shadowColor = 'transparent';
      context.globalCompositeOperation = 'source-over';

      for (let row = -5; row < rowCount; row += 1) {
        const baseY = row * spacing;
        const depth = (baseY + 100) / Math.max(height + 100, 1);
        const edgeFade = Math.max(0.35, Math.sin(Math.min(1, Math.max(0, depth)) * Math.PI));
        context.globalAlpha = 0.4 * edgeFade;
        context.beginPath();
        for (let x = -step; x <= width + step; x += step) {
          const y = pointY(x, baseY, row, time);
          if (x === -step) context.moveTo(x, y);
          else context.lineTo(x, y);
        }
        context.stroke();
      }
      context.globalAlpha = 1;
    }

    function animate(time) {
      if (!visible || reducedMotion.matches) return;
      animationFrame = requestAnimationFrame(animate);
      const minimumFrameTime = coarsePointer ? 42 : 33;
      if (time - lastFrame < minimumFrameTime) return;
      lastFrame = time;
      pointer.x += (pointer.targetX - pointer.x) * 0.075;
      pointer.y += (pointer.targetY - pointer.y) * 0.075;
      pointer.strength += (pointer.targetStrength - pointer.strength) * 0.065;
      while (ripples.length && time - ripples[0].startedAt > rippleDuration) ripples.shift();
      draw(time);
    }

    function startAnimation() {
      cancelAnimationFrame(animationFrame);
      if (visible && !reducedMotion.matches) animationFrame = requestAnimationFrame(animate);
      else draw(0);
    }

    function isBackgroundExposed(x, y) {
      if (document.querySelector('dialog[open]')) return false;
      const element = document.elementFromPoint(x, y);
      return !element?.closest(uiBlockers);
    }

    function movePointer(event) {
      if (!isBackgroundExposed(event.clientX, event.clientY)) {
        pointer.targetStrength = 0;
        return;
      }
      pointer.targetX = event.clientX;
      pointer.targetY = event.clientY;
      pointer.targetStrength = event.pointerType === 'touch' ? 0.72 : 1;
    }

    function pressBackground(event) {
      movePointer(event);
      if (reducedMotion.matches || !isBackgroundExposed(event.clientX, event.clientY)) return;
      if (event.pointerType === 'mouse' && event.button !== 0) return;
      ripples.push({ x: event.clientX, y: event.clientY, startedAt: performance.now() });
      if (ripples.length > 4) ripples.shift();
    }

    function releasePointer() {
      pointer.targetStrength = 0;
    }

    function handleVisibility() {
      visible = !document.hidden;
      startAnimation();
    }

    function handleTheme() {
      readColors();
      draw(performance.now());
    }

    resize();
    startAnimation();
    window.addEventListener('resize', resize, { passive: true });
    window.addEventListener('pointermove', movePointer, { passive: true });
    window.addEventListener('pointerdown', pressBackground, { passive: true });
    window.addEventListener('pointerup', releasePointer, { passive: true });
    document.documentElement.addEventListener('pointerleave', releasePointer, { passive: true });
    document.addEventListener('visibilitychange', handleVisibility);
    reducedMotion.addEventListener('change', startAnimation);
    window.addEventListener('converter-theme-change', handleTheme);

    return () => {
      cancelAnimationFrame(animationFrame);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', movePointer);
      window.removeEventListener('pointerdown', pressBackground);
      window.removeEventListener('pointerup', releasePointer);
      document.documentElement.removeEventListener('pointerleave', releasePointer);
      document.removeEventListener('visibilitychange', handleVisibility);
      reducedMotion.removeEventListener('change', startAnimation);
      window.removeEventListener('converter-theme-change', handleTheme);
    };
  });
</script>

<canvas bind:this={canvas} class="wave-background" aria-hidden="true"></canvas>
