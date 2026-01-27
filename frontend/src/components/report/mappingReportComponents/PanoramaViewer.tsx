import React, { useEffect, useRef } from 'react';
import { Viewer } from '@photo-sphere-viewer/core';
import '@photo-sphere-viewer/core/index.css';

interface PanoramaViewerProps {
  imageUrl: string; // URL of the panorama image
}

export function PanoramaViewer({ imageUrl }: PanoramaViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);

  useEffect(() => {
    if (containerRef.current && !viewerRef.current) {
      viewerRef.current = new Viewer({
        container: containerRef.current,
        panorama: imageUrl,
        minFov: 8,
        maxFov: 120,
      });
    }

    return () => {
      viewerRef.current?.destroy();
      viewerRef.current = null;
    };
  }, [imageUrl]);

  return <div ref={containerRef} className="w-full h-full" />;
};

