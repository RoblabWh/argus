// src/hooks/useReportEvents.ts
//
// Server-Sent Events client for live report updates (see api/SSE_MIGRATION_PLAN.md).
//
// One EventSource per report page streams typed events for every processing
// domain. Each event is translated into the react-query cache entries the
// existing polling hooks own (["report-process"], ["colmap-status"],
// ["detectionStatus"], ["autoDescription"], ["reconstruction-status"]), so all
// consuming components keep working unchanged — the data just arrives by push.
//
// Fallback: `sseActive` is false until the stream opens and flips back to
// false when the connection cannot be re-established within FAIL_AFTER_MS.
// Callers pass it as the `suspend` option to the polling hooks, so polling
// resumes automatically whenever SSE is down (and SSE is retried lazily).
import { createContext, useContext, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getMapById, getNewDetections, getReportEventsUrl } from "@/api";
import type { Map as OrthoMap } from "@/types/map";
import type { Detection } from "@/types/detection";

// Lets deeply nested cards (DetectionCard, AutoDescriptionCard,
// ColmapStatusIndicator) suspend their polling without prop-drilling.
// Default false = components outside a provider keep polling as before.
export const SseActiveContext = createContext(false);
export const useSseActive = () => useContext(SseActiveContext);

/** Envelope published by the backend/workers (the cross-container contract). */
interface ReportEvent {
  report_id: number;
  type: string;
  status: string | null;
  progress: number | null;
  message: string | null;
  data: Record<string, unknown>;
  ts: number;
}

const FAIL_AFTER_MS = 10_000; // give EventSource's own retries this long before falling back
const RETRY_AFTER_MS = 60_000; // while on polling fallback, retry SSE this often

/** Drop null/undefined so partial events merge without erasing cached fields. */
function defined(obj: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== null && v !== undefined)
  );
}

export function useReportEvents(reportId: number) {
  const queryClient = useQueryClient();
  const [sseActive, setSseActive] = useState(false);

  useEffect(() => {
    if (!reportId) return;

    let es: EventSource | null = null;
    let disposed = false;
    let failTimer: ReturnType<typeof setTimeout> | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    /** Merge a status event into a status-query cache entry. */
    const applyStatus = (
      key: unknown[],
      ev: ReportEvent,
      extra?: Record<string, unknown>
    ) => {
      queryClient.setQueryData(key, (prev: any) => ({
        report_id: reportId,
        ...(prev ?? {}),
        ...defined({ status: ev.status, progress: ev.progress, message: ev.message }),
        ...(extra ?? {}),
      }));
    };

    /** Fetch one freshly generated map and append it to the maps cache. */
    const fetchAndAppendMap = (mapId: number) => {
      getMapById(reportId, mapId)
        .then((map) => {
          queryClient.setQueryData(
            ["maps", reportId],
            (old: OrthoMap[] | undefined) => {
              // No cache yet → the initial maps fetch will include this map anyway.
              if (!old) return old;
              return old.some((m) => m.id === map.id)
                ? old.map((m) => (m.id === map.id ? map : m))
                : [...old, map];
            }
          );
          queryClient.invalidateQueries({ queryKey: ["mapsSlim", reportId] });
        })
        .catch(() => {
          /* the full maps refetch on "completed" is the safety net */
        });
    };

    /** Same known-ids incremental merge as useFetchNewDetections. */
    const fetchNewDetectionsIntoCache = () => {
      const cached = queryClient.getQueryData<Detection[]>(["detections", reportId]);
      const knownIds = (cached ?? []).map((d) => d.id);
      getNewDetections(reportId, knownIds)
        .then((fresh) => {
          if (!fresh.length) return;
          queryClient.setQueryData(
            ["detections", reportId],
            (old: Detection[] | undefined) => {
              const base = old ?? [];
              const existing = new Set(base.map((d) => d.id));
              return [...base, ...fresh.filter((d) => !existing.has(d.id))];
            }
          );
        })
        .catch(() => {
          /* the invalidate on "finished" is the safety net */
        });
    };

    const parse = (e: MessageEvent): ReportEvent | null => {
      try {
        return JSON.parse(e.data) as ReportEvent;
      } catch {
        return null;
      }
    };

    const onSnapshot = (e: MessageEvent) => {
      const snap = parse(e) as any;
      if (!snap) return;

      // Report status/progress: merge onto the last full report we have —
      // never seed the cache with a partial object (components expect a full
      // Report in ["report-process"]).
      queryClient.setQueryData(["report-process", reportId], (prev: any) => {
        const base = prev ?? queryClient.getQueryData(["report", reportId]);
        if (!base) return undefined; // leave cache unchanged
        return { ...base, status: snap.report.status, progress: snap.report.progress };
      });

      if (snap.colmap) queryClient.setQueryData(["colmap-status", reportId], snap.colmap);
      if (snap.detection) queryClient.setQueryData(["detectionStatus", reportId], snap.detection);
      if (snap.description) queryClient.setQueryData(["autoDescription", reportId], snap.description);
      if (snap.reconstruction)
        queryClient.setQueryData(["reconstruction-status", reportId], snap.reconstruction);

      // Maps that appeared while we were disconnected
      const cachedMaps = queryClient.getQueryData<OrthoMap[]>(["maps", reportId]);
      if (cachedMaps && Array.isArray(snap.map_ids)) {
        snap.map_ids
          .filter((id: number) => !cachedMaps.some((m) => m.id === id))
          .forEach((id: number) => fetchAndAppendMap(id));
      }
    };

    const onReportStatus = (e: MessageEvent) => {
      const ev = parse(e);
      if (!ev) return;
      queryClient.setQueryData(["report-process", reportId], (prev: any) => {
        const base = prev ?? queryClient.getQueryData(["report", reportId]);
        if (!base) return undefined;
        return { ...base, ...defined({ status: ev.status, progress: ev.progress }) };
      });
    };

    const onColmapStatus = (e: MessageEvent) => {
      const ev = parse(e);
      if (!ev) return;
      applyStatus(
        ["colmap-status", reportId],
        ev,
        ev.data?.has_reconstruction !== undefined
          ? { has_reconstruction: ev.data.has_reconstruction }
          : undefined
      );
    };

    const onDetectionStatus = (e: MessageEvent) => {
      const ev = parse(e);
      if (!ev) return;
      applyStatus(["detectionStatus", reportId], ev);
      if (ev.status === "finished") {
        // DetectionCard also invalidates on its terminal tick; this covers the
        // case where the card is not mounted.
        queryClient.invalidateQueries({ queryKey: ["detections", reportId] });
        queryClient.invalidateQueries({ queryKey: ["fireMap", reportId] });
      }
    };

    const onDescriptionStatus = (e: MessageEvent) => {
      const ev = parse(e);
      if (!ev) return;
      const description = (ev.data?.description as string | undefined) ?? undefined;
      applyStatus(
        ["autoDescription", reportId],
        ev,
        description !== undefined ? { description } : undefined
      );
    };

    const onReconstructionStatus = (e: MessageEvent) => {
      const ev = parse(e);
      if (!ev) return;
      applyStatus(["reconstruction-status", reportId], ev);
      if (ev.status === "completed" || ev.status === "error") {
        queryClient.invalidateQueries({ queryKey: ["reconstruction-results", reportId] });
      }
    };

    const onMapCreated = (e: MessageEvent) => {
      const ev = parse(e);
      const mapId = ev?.data?.map_id;
      if (typeof mapId === "number") fetchAndAppendMap(mapId);
      // A new (re)mapping run means new map elements — the temperature
      // overlay is derived from them (prefix-matches all clip variants).
      queryClient.invalidateQueries({ queryKey: ["thermalMap", reportId] });
    };

    const onDetectionsAdded = () => {
      fetchNewDetectionsIntoCache();
      // The server-generated fire overlay reflects the detections table;
      // refetch happens lazily (only while the fire layer is enabled).
      queryClient.invalidateQueries({ queryKey: ["fireMap", reportId] });
    };

    const scheduleRetry = () => {
      if (disposed || retryTimer) return;
      retryTimer = setTimeout(() => {
        retryTimer = null;
        connect();
      }, RETRY_AFTER_MS);
    };

    const connect = () => {
      if (disposed) return;
      es = new EventSource(getReportEventsUrl(reportId));

      es.onopen = () => {
        if (failTimer) {
          clearTimeout(failTimer);
          failTimer = null;
        }
        setSseActive(true);
      };

      es.onerror = () => {
        // EventSource retries on its own; only give up (and let polling take
        // over) when it can't reopen within FAIL_AFTER_MS.
        if (!failTimer) {
          failTimer = setTimeout(() => {
            failTimer = null;
            es?.close();
            es = null;
            setSseActive(false);
            scheduleRetry();
          }, FAIL_AFTER_MS);
        }
      };

      es.addEventListener("snapshot", onSnapshot);
      es.addEventListener("report_status", onReportStatus);
      es.addEventListener("colmap_status", onColmapStatus);
      es.addEventListener("detection_status", onDetectionStatus);
      es.addEventListener("description_status", onDescriptionStatus);
      es.addEventListener("reconstruction_status", onReconstructionStatus);
      es.addEventListener("map_created", onMapCreated);
      es.addEventListener("detections_added", onDetectionsAdded);
    };

    connect();

    return () => {
      disposed = true;
      if (failTimer) clearTimeout(failTimer);
      if (retryTimer) clearTimeout(retryTimer);
      es?.close();
      setSseActive(false);
    };
  }, [reportId, queryClient]);

  return { sseActive };
}
