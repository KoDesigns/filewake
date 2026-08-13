export async function getFormats() {
  const response = await fetch('/api/formats', { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('The converter is unavailable.');
  return response.json();
}

export async function getInfo() {
  const response = await fetch('/api/info', { headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('The converter is unavailable.');
  return response.json();
}

export async function inspectFile(file) {
  const body = new FormData();
  body.append('file', file, file.name);
  const response = await fetch('/api/inspect', { method: 'POST', body });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.message || 'This file could not be inspected.');
  return payload;
}

export function convertFile(file, outputFormat, onUploadProgress) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open('POST', '/api/convert');
    request.responseType = 'blob';
    request.setRequestHeader('Accept', 'application/octet-stream, application/json');
    request.upload.onprogress = (event) => {
      if (event.lengthComputable) onUploadProgress(Math.round((event.loaded / event.total) * 100));
    };
    request.onerror = () => reject(new Error('The connection to the converter was lost.'));
    request.onload = async () => {
      if (request.status >= 200 && request.status < 300) {
        const disposition = request.getResponseHeader('Content-Disposition') || '';
        const match = disposition.match(/filename="?([^";]+)"?/i);
        resolve({
          blob: request.response,
          filename: match?.[1] || `converted.${outputFormat}`,
          engine: request.getResponseHeader('X-Conversion-Engine') || 'converter'
        });
        return;
      }
      try {
        const payload = JSON.parse(await request.response.text());
        reject(new Error(payload.message || 'Conversion failed.'));
      } catch {
        reject(new Error('Conversion failed.'));
      }
    };
    const body = new FormData();
    body.append('file', file, file.name);
    body.append('output_format', outputFormat);
    request.send(body);
  });
}

export async function runPool(tasks, concurrency = 2) {
  const queue = [...tasks];
  const workers = Array.from({ length: Math.min(concurrency, queue.length) }, async () => {
    while (queue.length) {
      const task = queue.shift();
      if (task) await task();
    }
  });
  await Promise.all(workers);
}
