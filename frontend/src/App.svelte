<script>
  import { onMount } from 'svelte';
  import JSZip from 'jszip';
  import FileRow from './components/FileRow.svelte';
  import Icon from './components/Icon.svelte';
  import WaveBackground from './components/WaveBackground.svelte';
  import WaveLoader from './components/WaveLoader.svelte';
  import { convertFile, getFormats, getInfo, inspectFile, runPool } from './lib/api.js';

  const themeStorageKey = 'converter-theme';
  let input;
  let items = [];
  let formats = {};
  let limits = { max_file_size_mb: 2048, max_batch_files: 50, max_batch_size_mb: 4096 };
  let loadingFormats = true;
  let serviceError = '';
  let dragging = false;
  let globalOutput = '';
  let converting = false;
  let zipBusy = false;
  let theme = 'light';
  let fallbackIdCounter = 0;

  $: successful = items.filter((item) => item.status === 'done');
  $: ready = items.filter((item) => item.status === 'ready' || item.status === 'failed');
  $: globalOutputs = [...new Set(items.flatMap((item) => item.outputs))].sort();

  onMount(() => {
    theme = document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light';
    const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
    const followSystemTheme = (event) => {
      try {
        if (localStorage.getItem(themeStorageKey)) return;
      } catch {
        return;
      }
      applyTheme(event.matches ? 'dark' : 'light', false);
    };
    systemTheme.addEventListener('change', followSystemTheme);

    Promise.all([getFormats(), getInfo()])
      .then(([formatPayload, infoPayload]) => {
        formats = formatPayload.categories;
        limits = infoPayload.limits;
      })
      .catch((error) => { serviceError = error.message; })
      .finally(() => { loadingFormats = false; });
    return () => {
      systemTheme.removeEventListener('change', followSystemTheme);
      items.forEach(revokeItem);
    };
  });

  function applyTheme(nextTheme, persist) {
    theme = nextTheme;
    document.documentElement.dataset.theme = nextTheme;
    document.documentElement.style.colorScheme = nextTheme;
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) themeColor.content = nextTheme === 'dark' ? '#171717' : '#ffffff';
    if (persist) {
      try {
        localStorage.setItem(themeStorageKey, nextTheme);
      } catch {
        // The visual switch still works when persistent browser storage is unavailable.
      }
    }
    window.dispatchEvent(new CustomEvent('converter-theme-change', { detail: nextTheme }));
  }

  function toggleTheme() {
    applyTheme(theme === 'dark' ? 'light' : 'dark', true);
  }

  function revokeResult(item) {
    if (item.resultUrl) URL.revokeObjectURL(item.resultUrl);
  }

  function revokeItem(item) {
    revokeResult(item);
    if (item.sourceUrl) URL.revokeObjectURL(item.sourceUrl);
  }

  function update(id, values) {
    items = items.map((item) => item.id === id ? { ...item, ...values } : item);
  }

  function registryOutputs(source) {
    const category = Object.values(formats).find((entries) => source in entries);
    return category?.[source] || [];
  }

  function createClientId() {
    const browserCrypto = globalThis.crypto;
    if (typeof browserCrypto?.randomUUID === 'function') return browserCrypto.randomUUID();
    if (typeof browserCrypto?.getRandomValues === 'function') {
      const bytes = browserCrypto.getRandomValues(new Uint8Array(16));
      bytes[6] = (bytes[6] & 0x0f) | 0x40;
      bytes[8] = (bytes[8] & 0x3f) | 0x80;
      const hex = [...bytes].map((value) => value.toString(16).padStart(2, '0')).join('');
      return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
    }
    fallbackIdCounter += 1;
    return `file-${Date.now().toString(36)}-${fallbackIdCounter.toString(36)}`;
  }

  async function inspectOne(item) {
    update(item.id, { status: 'inspecting', error: '' });
    try {
      const result = await inspectFile(item.file);
      const allowed = registryOutputs(result.detected_format);
      const outputs = result.possible_outputs.filter((output) => allowed.includes(output));
      update(item.id, {
        status: outputs.length ? 'ready' : 'failed', detectedFormat: result.detected_format,
        category: result.category, outputs,
        outputFormat: outputs.includes(result.default_output) ? result.default_output : outputs[0] || '',
        mismatch: result.mismatch,
        error: outputs.length ? '' : 'No safe output is available for this file.'
      });
    } catch (error) {
      update(item.id, { status: 'failed', error: error.message, outputs: [] });
    }
  }

  async function addFiles(fileList) {
    serviceError = '';
    const known = new Set(items.map((item) => `${item.file.name}:${item.file.size}:${item.file.lastModified}`));
    const candidates = [...fileList].filter((file) => !known.has(`${file.name}:${file.size}:${file.lastModified}`));
    const remainingCount = Math.max(0, limits.max_batch_files - items.length);
    const remainingBytes = Math.max(0, limits.max_batch_size_mb * 1024 ** 2 - items.reduce((total, item) => total + item.file.size, 0));
    let acceptedBytes = 0;
    const additions = candidates
      .filter((file) => file.size <= limits.max_file_size_mb * 1024 ** 2)
      .filter((file) => {
        if (acceptedBytes + file.size > remainingBytes) return false;
        acceptedBytes += file.size;
        return true;
      })
      .slice(0, remainingCount)
      .filter((file) => !known.has(`${file.name}:${file.size}:${file.lastModified}`))
      .map((file) => ({
        id: createClientId(), file, status: 'inspecting', progress: 0, outputs: [],
        outputFormat: '', detectedFormat: '', category: '', mismatch: false,
        sourceUrl: URL.createObjectURL(file), resultUrl: '', resultName: '', resultBlob: null, error: ''
      }));
    items = [...items, ...additions];
    if (additions.length < candidates.length) {
      serviceError = `Some files were skipped because this server allows ${limits.max_batch_files} files, ${limits.max_batch_size_mb} MB per batch, and ${limits.max_file_size_mb} MB per file.`;
    }
    await runPool(additions.map((item) => () => inspectOne(item)), 2);
    if (input) input.value = '';
  }

  function removeItem(id) {
    const item = items.find((entry) => entry.id === id);
    if (item) revokeItem(item);
    items = items.filter((entry) => entry.id !== id);
  }

  function setFormat(id, outputFormat) {
    const item = items.find((entry) => entry.id === id);
    if (item) revokeResult(item);
    update(id, { outputFormat, status: 'ready', error: '', resultUrl: '', resultName: '', resultBlob: null });
  }

  function applyGlobal() {
    if (!globalOutput) return;
    items = items.map((item) => item.outputs.includes(globalOutput) && ['ready', 'failed'].includes(item.status)
      ? { ...item, outputFormat: globalOutput, status: 'ready', error: '' }
      : item);
  }

  async function convertOne(item) {
    if (!item.outputFormat || !item.outputs.length) return;
    revokeResult(item);
    update(item.id, { status: 'uploading', progress: 0, error: '', resultUrl: '', resultBlob: null });
    try {
      const result = await convertFile(item.file, item.outputFormat, (progress) => {
        update(item.id, { status: progress >= 100 ? 'converting' : 'uploading', progress });
      });
      update(item.id, {
        status: 'done', resultBlob: result.blob,
        resultUrl: URL.createObjectURL(result.blob), resultName: result.filename,
        engine: result.engine, progress: 100
      });
    } catch (error) {
      update(item.id, { status: 'failed', error: error.message });
    }
  }

  async function convertAll() {
    converting = true;
    const jobs = items.filter((item) => ['ready', 'failed'].includes(item.status) && item.outputFormat && item.outputs.length);
    await runPool(jobs.map((item) => () => convertOne(item)), 2);
    converting = false;
  }

  async function downloadAll() {
    zipBusy = true;
    try {
      const archive = new JSZip();
      successful.forEach((item) => archive.file(item.resultName, item.resultBlob));
      const blob = await archive.generateAsync({ type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 5 } });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'converted-files.zip';
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } finally {
      zipBusy = false;
    }
  }

  function clearAll() {
    items.forEach(revokeItem);
    items = [];
    globalOutput = '';
  }

  function drop(event) {
    dragging = false;
    addFiles(event.dataTransfer.files);
  }
</script>

<svelte:head><title>Filewake — private file conversion</title></svelte:head>

<WaveBackground />

<button
  class="theme-toggle"
  type="button"
  aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
  title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
  on:click={toggleTheme}
>
  <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={18} />
</button>

<main>
  {#if serviceError}
    <div class="service-error" role="alert">{serviceError} Check that the API is running, then reload this page.</div>
  {/if}

  <section class="workspace" aria-busy={loadingFormats}>
    <button
      class:dragging
      class:with-files={items.length > 0}
      class="drop-zone"
      type="button"
      on:click={() => input?.click()}
      on:dragenter|preventDefault={() => dragging = true}
      on:dragover|preventDefault={() => dragging = true}
      on:dragleave|preventDefault={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) dragging = false; }}
      on:drop|preventDefault={drop}
      disabled={loadingFormats || Boolean(serviceError)}
    >
      <span class="drop-icon">
        {#if loadingFormats}<WaveLoader size={32} />{:else}<Icon name="upload" size={26} />{/if}
      </span>
      <span class="drop-main">{loadingFormats ? 'Loading converter' : items.length ? 'Add more files' : 'Drop files here'}</span>
      <span class="drop-sub">{loadingFormats ? 'Checking available formats' : items.length ? 'Drop or browse' : 'Images · Video · Audio · Documents · Fonts'}</span>
      {#if !items.length}<span class="browse-label">Browse files</span>{/if}
    </button>
    <input bind:this={input} class="visually-hidden" type="file" multiple on:change={(event) => addFiles(event.currentTarget.files)} />

    {#if items.length}
      <div class="file-list" aria-label="Files to convert">
        {#each items as item (item.id)}
          <FileRow
            {item}
            on:remove={() => removeItem(item.id)}
            on:format={(event) => setFormat(item.id, event.detail)}
            on:retry={() => item.outputs.length ? convertOne(item) : inspectOne(item)}
          />
        {/each}
      </div>

      <div class="bulk-bar">
        <div class="global-control">
          <label for="global-output">Set compatible files to</label>
          <div>
            <select id="global-output" bind:value={globalOutput} disabled={!globalOutputs.length || converting}>
              <option value="">Choose format</option>
              {#each globalOutputs as output}<option value={output}>{output.toUpperCase()}</option>{/each}
            </select>
            <button type="button" class="apply-button" on:click={applyGlobal} disabled={!globalOutput || converting}>Apply</button>
          </div>
        </div>
        <div class="primary-actions">
          {#if successful.length > 1}
            <button type="button" class="secondary-button" on:click={downloadAll} disabled={zipBusy}>
              {#if zipBusy}<WaveLoader size={26} />{:else}<Icon name="download" size={18} />{/if}
              {zipBusy ? 'Preparing ZIP' : 'Download all'}
            </button>
          {/if}
          <button type="button" class="convert-button" on:click={convertAll} disabled={converting || !ready.some((item) => item.outputFormat)}>
            {#if converting}<WaveLoader size={27} contrast />{/if}
            {converting ? 'Converting files' : `Convert ${ready.filter((item) => item.outputFormat).length || ''} ${ready.length === 1 ? 'file' : 'files'}`}
          </button>
        </div>
      </div>

      <button class="clear-button" type="button" on:click={clearAll} disabled={converting}>Clear everything</button>
    {/if}
  </section>

  <footer>
    <div class="footer-signature">
      <span class="footer-logo" aria-hidden="true">
        <img class="footer-logo-light" src="/Logo_Silhuet_Black.svg" alt="" />
        <img class="footer-logo-dark" src="/Logo_Silhuet_White.svg" alt="" />
      </span>
      <span>Filewake is made by Kodesign for personal use only.</span>
    </div>
    <a href="/api/openapi.json">OpenAPI schema</a>
  </footer>
</main>
