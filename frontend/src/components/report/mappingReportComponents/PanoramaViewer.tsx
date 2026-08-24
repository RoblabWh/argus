import React, { useEffect, useRef, useState } from 'react';
import { Viewer } from '@photo-sphere-viewer/core';
import '@photo-sphere-viewer/core/index.css';
import { Button } from '@/components/ui/button';

interface PanoramaViewerProps {
  imageUrl: string; // URL of the panorama image
}

const LOAD_ERROR = 'Panorama could not be loaded.';

export function PanoramaViewer({ imageUrl }: PanoramaViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let viewer: Viewer | null = null;

    const timeout = setTimeout(() => {
      if (!containerRef.current || viewerRef.current) return;
    if (containerRef.current && !viewerRef.current) {
      viewer= new Viewer({
        container: containerRef.current,
        panorama: imageUrl,
        minFov: 8,
        maxFov: 120,
      });
      // The initial load happens inside the constructor, so its failure can only
      // be observed through this event (setPanorama below covers later loads).
      viewer.addEventListener('panorama-error', ({ error: err }) => {
        console.error('Error occurred while loading panorama:', err);
        setError(LOAD_ERROR);
      });
      viewer.addEventListener('panorama-loaded', () => setError(null));
      viewerRef.current = viewer;
    }
    }, 0); // Delay to ensure the container is rendered

    return () => {
      clearTimeout(timeout);
      const toDestroy = viewer;
      viewerRef.current = null;
      try {
        toDestroy?.destroy();
      } catch (error) {
        console.error('Error occurred while destroying Viewer:', error);
      }
    };
  }, []);

  useEffect(() => {
    if (!viewerRef.current) return;
    setError(null);
    viewerRef.current.setPanorama(imageUrl).catch((err) => {
      console.error('Error occurred while loading panorama:', err);
      setError(LOAD_ERROR);
    });
  }, [imageUrl, reloadKey]);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="w-full h-full" />
      {error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-background/90 p-4 text-center">
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            Retry
          </Button>
        </div>
      )}
    </div>
  );
};
