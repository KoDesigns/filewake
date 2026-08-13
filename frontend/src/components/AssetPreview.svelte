<script>
  import { onDestroy, tick } from 'svelte';
  import Icon from './Icon.svelte';

  export let item;

  let previewMode = 'before';
  let lastResultUrl = '';
  let loadedKey = '';
  let imageFailed = false;
  let videoFailed = false;
  let audioFailed = false;
  let fontFailed = false;
  let mediaOpen = false;
  let mediaKind = '';
  let mediaDialog;
  let audioElement;
  let overlayVideo;
  let closeButton;
  let triggerButton;
  let playing = false;
  let currentTime = 0;
  let duration = 0;
  let fontFace;
  let fontFamily = '';
  let fontLoadToken = 0;
  let previousBodyOverflow = '';

  $: canCompare = Boolean(item.resultUrl);
  $: if (item.resultUrl && item.resultUrl !== lastResultUrl) {
    lastResultUrl = item.resultUrl;
    previewMode = 'after';
  }
  $: if (!item.resultUrl && previewMode === 'after') previewMode = 'before';
  $: activeUrl = previewMode === 'after' && item.resultUrl ? item.resultUrl : item.sourceUrl;
  $: stageLabel = previewMode === 'after' ? 'Converted' : 'Original';
  $: assetKey = `${item.category}:${activeUrl}`;
  $: if (assetKey !== loadedKey) {
    loadedKey = assetKey;
    resetAssetState();
  }

  function resetAssetState() {
    imageFailed = false;
    videoFailed = false;
    audioFailed = false;
    playing = false;
    currentTime = 0;
    duration = 0;
    if (audioElement) {
      audioElement.pause();
      audioElement.load();
    }
    if (item.category === 'font') loadFont(activeUrl);
  }

  async function loadFont(url) {
    const token = ++fontLoadToken;
    fontFailed = false;
    fontFamily = '';
    if (fontFace) {
      document.fonts.delete(fontFace);
      fontFace = null;
    }
    if (!url || typeof FontFace === 'undefined') {
      fontFailed = true;
      return;
    }
    try {
      const face = new FontFace(`converter-preview-${item.id}`, `url(${url})`);
      await face.load();
      if (token !== fontLoadToken) return;
      document.fonts.add(face);
      fontFace = face;
      fontFamily = face.family;
    } catch {
      if (token === fontLoadToken) fontFailed = true;
    }
  }

  function selectMode(mode) {
    if (mode === 'after' && !item.resultUrl) return;
    previewMode = mode;
    if (mediaOpen && mediaKind === 'video') {
      tick().then(() => overlayVideo?.play().catch(() => {}));
    }
  }

  function toggleMode() {
    selectMode(previewMode === 'after' ? 'before' : 'after');
  }

  function setVideoFrame(event) {
    const video = event.currentTarget;
    if (Number.isFinite(video.duration) && video.duration > 0.1 && video.currentTime === 0) {
      video.currentTime = Math.min(0.1, video.duration / 10);
    }
  }

  async function openMedia(event, kind) {
    triggerButton = event.currentTarget;
    previousBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    mediaKind = kind;
    mediaOpen = true;
    await tick();
    mediaDialog?.showModal();
    closeButton?.focus();
  }

  function closeMedia() {
    overlayVideo?.pause();
    if (mediaDialog?.open) mediaDialog.close();
    mediaOpen = false;
    document.body.style.overflow = previousBodyOverflow;
    tick().then(() => triggerButton?.focus());
  }

  async function toggleAudio() {
    if (!audioElement || audioFailed) return;
    if (audioElement.paused) {
      try {
        await audioElement.play();
      } catch {
        audioFailed = true;
      }
    } else {
      audioElement.pause();
    }
  }

  function updateDuration(event) {
    const value = event.currentTarget.duration;
    duration = Number.isFinite(value) ? value : 0;
  }

  function seekAudio(event) {
    if (!audioElement) return;
    audioElement.currentTime = Number(event.currentTarget.value);
    currentTime = audioElement.currentTime;
  }

  function timeLabel(seconds) {
    if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
    const minutes = Math.floor(seconds / 60);
    return `${minutes}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
  }

  onDestroy(() => {
    fontLoadToken += 1;
    if (fontFace) document.fonts.delete(fontFace);
    if (mediaOpen) document.body.style.overflow = previousBodyOverflow;
  });
</script>

{#if item.category === 'image'}
  <div class="asset-preview-tile image-preview-tile">
    {#if imageFailed}
      <span class="preview-fallback"><Icon name="file" size={18} /></span>
    {:else}
      <button class="image-open-button" type="button" on:click={(event) => openMedia(event, 'image')} aria-label={`Enlarge ${stageLabel.toLowerCase()} image`}>
        <img src={activeUrl} alt="" on:error={() => imageFailed = true} />
      </button>
    {/if}
    {#if canCompare}
      <button class="preview-stage" type="button" on:click={toggleMode} aria-label={`Show ${previewMode === 'after' ? 'original' : 'converted'} image`}>
        {previewMode === 'after' ? 'After' : 'Before'}
      </button>
    {/if}
  </div>
{:else if item.category === 'video'}
  <div class="asset-preview-tile video-preview-tile">
    {#if !videoFailed}
      <video src={activeUrl} muted playsinline preload="metadata" aria-hidden="true" on:loadedmetadata={setVideoFrame} on:error={() => videoFailed = true}></video>
    {:else}
      <span class="preview-fallback"><Icon name="video" size={19} /></span>
    {/if}
    <button class="video-open-button" type="button" on:click={(event) => openMedia(event, 'video')} disabled={videoFailed} aria-label={`Play ${stageLabel.toLowerCase()} video`}>
      <Icon name="play" size={16} />
    </button>
    {#if canCompare}
      <button class="preview-stage" type="button" on:click={toggleMode} aria-label={`Show ${previewMode === 'after' ? 'original' : 'converted'} video`}>
        {previewMode === 'after' ? 'After' : 'Before'}
      </button>
    {/if}
  </div>
{:else if item.category === 'font'}
  <div class="asset-preview-tile font-preview-tile" class:preview-unavailable={fontFailed} style:font-family={fontFamily || undefined}>
    <span aria-hidden="true">Ag</span>
    {#if canCompare}
      <button class="preview-stage" type="button" on:click={toggleMode} aria-label={`Show ${previewMode === 'after' ? 'original' : 'converted'} font`}>
        {previewMode === 'after' ? 'After' : 'Before'}
      </button>
    {/if}
  </div>
  <p class="font-specimen" class:preview-unavailable={fontFailed} style:font-family={fontFamily || undefined}>
    PACK MY BOX with five dozen liquor jugs.
  </p>
{:else}
  <div class="file-mark" data-category={item.category || 'unknown'}>
    {#if item.category === 'audio'}
      <Icon name="audio" size={19} />
    {:else if item.status === 'done'}
      <Icon name="check" size={19} />
    {:else}
      <Icon name="file" size={19} />
    {/if}
  </div>
{/if}

{#if item.category === 'audio'}
  <div class="audio-preview" class:preview-unavailable={audioFailed}>
    <button class="audio-play-button" type="button" on:click={toggleAudio} disabled={audioFailed} aria-label={playing ? 'Pause audio preview' : 'Play audio preview'}>
      <Icon name={playing ? 'pause' : 'play'} size={15} />
    </button>
    <div class="audio-timeline">
      <input
        type="range"
        min="0"
        max={duration || 0}
        step="0.01"
        value={currentTime}
        disabled={audioFailed || !duration}
        aria-label="Audio preview position"
        on:input={seekAudio}
      />
      <span>{audioFailed ? 'Preview unavailable' : `${timeLabel(currentTime)} / ${timeLabel(duration)}`}</span>
    </div>
    {#if canCompare}
      <button class="audio-stage-button" type="button" on:click={toggleMode} aria-label={`Play ${previewMode === 'after' ? 'original' : 'converted'} audio`}>
        {stageLabel}
      </button>
    {/if}
    <audio
      bind:this={audioElement}
      src={activeUrl}
      preload="metadata"
      on:loadedmetadata={updateDuration}
      on:durationchange={updateDuration}
      on:timeupdate={(event) => currentTime = event.currentTarget.currentTime}
      on:play={() => playing = true}
      on:pause={() => playing = false}
      on:ended={() => playing = false}
      on:error={() => audioFailed = true}
    ></audio>
  </div>
{/if}

{#if mediaOpen}
  <dialog
    bind:this={mediaDialog}
    class="media-overlay"
    aria-label={`${mediaKind === 'video' ? 'Video' : 'Image'} preview for ${item.file.name}`}
    on:cancel|preventDefault={closeMedia}
    on:click={(event) => event.target === event.currentTarget && closeMedia()}
  >
    <div class="media-dialog" class:image-dialog={mediaKind === 'image'}>
      <header>
        <strong>{item.file.name}</strong>
        {#if canCompare}
          <div class="media-stage-switch" aria-label="Preview version">
            <button type="button" class:active={previewMode === 'before'} on:click={() => selectMode('before')}>Original</button>
            <button type="button" class:active={previewMode === 'after'} on:click={() => selectMode('after')}>Converted</button>
          </div>
        {/if}
        <button bind:this={closeButton} class="media-close-button" type="button" on:click={closeMedia} aria-label="Close media preview">
          <span>Close</span>
          <Icon name="close" size={19} />
        </button>
      </header>
      {#if mediaKind === 'video'}
        <!-- Uploaded videos do not include a separate caption resource to attach here. -->
        <!-- svelte-ignore a11y_media_has_caption -->
        <video bind:this={overlayVideo} src={activeUrl} controls autoplay playsinline></video>
      {:else}
        <img class="expanded-image" src={activeUrl} alt={`Preview of ${item.file.name}`} />
      {/if}
    </div>
  </dialog>
{/if}
