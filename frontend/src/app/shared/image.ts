/** Re-encode a browser image to a smaller JPEG so uploads stay light. */
export async function compressImageToFile(
  file: File,
  maxDimension: number,
  quality = 0.82,
  maxBytes?: number,
): Promise<File> {
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new Error('image_unreadable');
  }
  try {
    const scale = Math.min(1, maxDimension / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext('2d');
    if (!context) throw new Error('canvas_unavailable');
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);

    let currentQuality = quality;
    let blob = await canvasToBlob(canvas, currentQuality);
    while (maxBytes && blob && blob.size > maxBytes && currentQuality > 0.3) {
      currentQuality = Math.max(0.3, currentQuality - 0.1);
      blob = await canvasToBlob(canvas, currentQuality);
    }
    if (!blob) throw new Error('canvas_unavailable');
    if (maxBytes && blob.size > maxBytes) throw new Error('image_too_large');

    const baseName = file.name.replace(/\.[^.]+$/, '') || 'photo';
    return new File([blob], `${baseName}.jpg`, { type: 'image/jpeg' });
  } finally {
    bitmap.close();
  }
}

function canvasToBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob | null> {
  return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob), 'image/jpeg', quality));
}
