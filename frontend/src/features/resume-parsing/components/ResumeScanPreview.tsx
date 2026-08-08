import { useEffect, useRef, useState } from 'react';

import styles from './ResumeScanPreview.module.css';

type ResumeScanPreviewProps = {
  file: File;
};

/**
 * Shows the first page of the uploaded resume with a scan line sweeping over
 * it. Rendered only while the server is parsing, so the animation is always on.
 *
 * Images render straight from an object URL. PDFs are rasterised with pdf.js,
 * which is loaded lazily so the ~1 MB worker is only fetched once a PDF is
 * actually chosen. DOCX has no browser-renderable form, so it falls back to a
 * document glyph rather than a broken frame.
 */
export function ResumeScanPreview({ file }: ResumeScanPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [unrenderable, setUnrenderable] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    if (file.type.startsWith('image/')) {
      objectUrl = URL.createObjectURL(file);
      setImageUrl(objectUrl);
      return () => {
        if (objectUrl) URL.revokeObjectURL(objectUrl);
      };
    }

    if (file.type !== 'application/pdf') {
      setUnrenderable(true);
      return;
    }

    void (async () => {
      try {
        const pdfjs = await import('pdfjs-dist');
        const worker = await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
        pdfjs.GlobalWorkerOptions.workerSrc = worker.default;

        const buffer = await file.arrayBuffer();
        if (cancelled) return;

        const doc = await pdfjs.getDocument({ data: buffer }).promise;
        const page = await doc.getPage(1);
        const canvas = canvasRef.current;
        if (cancelled || !canvas) return;

        // Render at the card's width rather than the page's natural size, and
        // account for device pixel ratio so text stays legible on retina.
        const targetWidth = canvas.parentElement?.clientWidth ?? 420;
        const base = page.getViewport({ scale: 1 });
        const ratio = Math.min(window.devicePixelRatio || 1, 2);
        const viewport = page.getViewport({ scale: (targetWidth / base.width) * ratio });

        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.style.width = '100%';
        canvas.style.height = 'auto';

        const context = canvas.getContext('2d');
        if (!context) return;
        await page.render({ canvas, canvasContext: context, viewport }).promise;
      } catch {
        // A preview is decoration. If pdf.js cannot read the file the upload
        // itself is unaffected, so fall back quietly.
        if (!cancelled) setUnrenderable(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [file]);

  return (
    <figure className={styles.frame}>
      <div className={styles.page}>
        {imageUrl && <img src={imageUrl} alt="" />}
        {!imageUrl && !unrenderable && <canvas ref={canvasRef} />}
        {unrenderable && (
          <div className={styles.fallback} aria-hidden="true">
            <span>DOC</span>
          </div>
        )}
      </div>

      <div className={styles.beam} aria-hidden="true" />
      <div className={styles.grid} aria-hidden="true" />

      <figcaption className={styles.caption}>{file.name}</figcaption>
    </figure>
  );
}
