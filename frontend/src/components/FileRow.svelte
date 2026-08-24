<script>
  import { createEventDispatcher } from 'svelte';
  import AssetPreview from './AssetPreview.svelte';
  import Icon from './Icon.svelte';
  import WaveLoader from './WaveLoader.svelte';

  export let item;
  const dispatch = createEventDispatcher();

  const labels = {
    inspecting: 'Inspecting',
    ready: 'Ready',
    uploading: 'Uploading',
    converting: 'Converting',
    done: 'Done',
    failed: 'Failed'
  };

  function sizeLabel(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(0)} KB`;
    if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
    return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  }
</script>

<article
  class="file-row"
  class:has-audio={item.category === 'audio'}
  class:has-font={item.category === 'font'}
  class:is-busy={item.status === 'inspecting' || item.status === 'uploading' || item.status === 'converting'}
  aria-busy={item.status === 'inspecting' || item.status === 'uploading' || item.status === 'converting'}
>
  <AssetPreview {item} />

  <div class="file-identity">
    <strong title={item.file.name}>{item.file.name}</strong>
    <span>
      {item.detectedFormat ? item.detectedFormat.toUpperCase() : 'Reading type'}
      <i aria-hidden="true"></i>
      {sizeLabel(item.file.size)}
      {#if item.mismatch}<i aria-hidden="true"></i><em>Type corrected</em>{/if}
    </span>
  </div>

  <div class="file-choice">
    <label for={`format-${item.id}`}>Output</label>
    <select
      id={`format-${item.id}`}
      value={item.outputFormat}
      disabled={item.status !== 'ready' && item.status !== 'failed'}
      on:change={(event) => dispatch('format', event.currentTarget.value)}
    >
      {#each item.outputs as output}
        <option value={output}>{output.toUpperCase()}</option>
      {/each}
    </select>
  </div>

  <div class="file-state" aria-live="polite">
    {#if item.status === 'done'}
      <a class="download-link" href={item.resultUrl} download={item.resultName}>
        <Icon name="download" size={17} />
        Download
      </a>
    {:else if item.status === 'failed'}
      <button class="retry-button" type="button" on:click={() => dispatch('retry')}>
        <Icon name="retry" size={16} />
        Retry
      </button>
    {:else}
      {#if item.status !== 'ready'}<WaveLoader size={30} />{/if}
      <span>{labels[item.status]}</span>
      {#if item.status === 'uploading'}<small>{item.progress}%</small>{/if}
    {/if}
  </div>

  <button class="remove-button" type="button" aria-label={`Remove ${item.file.name}`} on:click={() => dispatch('remove')}>
    <Icon name="close" size={18} />
  </button>

  {#if item.status === 'uploading'}
    <div class="upload-progress" style={`--progress: ${item.progress}%`}></div>
  {/if}
  {#if item.error}<p class="row-error">{item.error}</p>{/if}
</article>
