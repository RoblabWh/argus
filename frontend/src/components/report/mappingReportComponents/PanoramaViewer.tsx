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
    viewerRef.current.setPanorama(imageUrl);
  }, [imageUrl]);

  return <div ref={containerRef} className="w-full h-full" />;
};

