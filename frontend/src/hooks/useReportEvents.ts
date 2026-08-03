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
// Demand-driven lifecycle (important — browsers allow only ~6 concurrent
// HTTP/1.1 connections per origin, shared across ALL tabs). A stream held for
// the lifetime of the page parks one of those six sockets forever, so ~6 open
// report tabs used to deadlock every other request to the API origin. Instead:
//
//   connect → snapshot → is anything actually processing?
//        busy  → keep streaming (this is what SSE is for)
//        quiet → close the socket and go idle; re-open briefly on tab focus,
//                on a slow heartbeat, or when this tab starts a job (wake()).
//
// So idle tabs hold zero sockets and any number of them can be open.
//
// Fallback: `suspendPolling` is false until the stream opens and flips back to
// false when the connection cannot be re-established within FAIL_AFTER_MS.
// Callers pass it as the `suspend` option to the polling hooks, so polling
// resumes automatically whenever SSE is down (and SSE is retried lazily).
// Crucially, a *deliberate* idle close keeps `suspendPolling` true — otherwise
// every idle tab would restart the 2s polls we just got rid of.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { getMapById, getNewDetections, getReportEventsUrl } from "@/api";
import type { Map as OrthoMap } from "@/types/map";
import type { Detection } from "@/types/detection";

export interface SseState {
  /** A stream is currently open and delivering events. */
  streaming: boolean;
  /** Polling hooks should stay quiet (streaming, or deliberately idle). */
  suspendPolling: boolean;
  /** Re-open the stream now — call after starting a job from this tab. */
  wake: () => void;
}

// Lets deeply nested cards (DetectionCard, AutoDescriptionCard,
// ColmapStatusIndicator) suspend their polling / wake the stream without
// prop-drilling. Default = components outside a provider keep polling as before.
const NO_SSE: SseState = { streaming: false, suspendPolling: false, wake: () => {} };
export const SseActiveContext = createContext<SseState>(NO_SSE);
export const useSseActive = () => useContext(SseActiveContext).suspendPolling;
export const useSseWake = () => useContext(SseActiveContext).wake;

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

/**
 * "connecting" — initial connect, outcome unknown (polling still runs, as before)
 * "streaming"  — socket open, events flowing
 * "idle"       — nothing processing, socket deliberately released
 * "fallback"   — SSE unreachable, the polling hooks own the updates
 */
type Phase = "connecting" | "streaming" | "idle" | "fallback";

const FAIL_AFTER_MS = 10_000; // give EventSource's own retries this long before falling back
const RETRY_AFTER_MS = 60_000; // while on polling fallback, retry SSE this often
const HEARTBEAT_MS = 60_000; // while idle, re-check state this often (short-lived connect)
// Quiet period before releasing the socket. Short for a report that has been
// quiet all along; promoted to the long value once we have seen work happen,
// because COLMAP is dispatched *after* mapping reports "completed" — the
// colmap_status event trails report_status by a few seconds.
const PROBE_GRACE_MS = 1_500;
const ACTIVE_GRACE_MS = 15_000;

// Which per-domain status values mean "still working". The report lifecycle is
// a closed set; the worker-owned domains are expressed as "anything that is not
// a terminal/absent marker", so an unrecognised state keeps the stream open
// rather than silently dropping updates.
const REPORT_BUSY = new Set(["queued", "preprocessing", "processing"]);
const DETECTION_QUIET = new Set(["finished", "failed", "error", "cancelled", "unknown", "none"]);
const DESCRIPTION_QUIET = new Set(["completed", "error", "no_description", "unknown", "none"]);
const RECONSTRUCTION_QUIET = new Set([
  "completed", "finished", "failed", "error", "cancelled", "unknown", "none",
]);
const COLMAP_QUIET = new Set(["completed", "error", "none", "unknown"]);

/** Absent status → not busy; otherwise busy unless it is a terminal marker. */
const busyUnless = (quiet: Set<string>) => (status: string | null | undefined) =>
  !!status && !quiet.has(status.toLowerCase());

const detectionBusy = busyUnless(DETECTION_QUIET);
const descriptionBusy = busyUnless(DESCRIPTION_QUIET);
const reconstructionBusy = busyUnless(RECONSTRUCTION_QUIET);
const colmapBusy = busyUnless(COLMAP_QUIET);
const reportBusy = (status: string | null | undefined) =>
  !!status && REPORT_BUSY.has(status.toLowerCase());

/** Drop null/undefined so partial events merge without erasing cached fields. */
function defined(obj: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== null && v !== undefined)
  );
}

export function useReportEvents(reportId: number): SseState {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<Phase>("connecting");

  // Stable identity for consumers; the effect swaps the implementation.
  const wakeRef = useRef<() => void>(() => {});
  const wake = useCallback(() => wakeRef.current(), []);

  useEffect(() => {
    if (!reportId) return;

    let es: EventSource | null = null;
    let disposed = false;
    let failTimer: ReturnType<typeof setTimeout> | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let idleTimer: ReturnType<typeof setTimeout> | null = null;
    let heartbeatTimer: ReturnType<typeof setTimeout> | null = null;

    // Last known state per domain, seeded by the snapshot and kept current by
    // every typed event — this is what decides whether the socket is worth holding.
    const busy = {
      report: false,
      detection: false,
      description: false,
      reconstruction: false,
      colmap: false,
    };
    const anythingBusy = () => Object.values(busy).some(Boolean);
    let graceMs = PROBE_GRACE_MS;

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

      // Full state in one frame → re-seed every domain at once.
      busy.report = reportBusy(snap.report?.status);
      busy.detection = detectionBusy(snap.detection?.status);
      busy.description = descriptionBusy(snap.description?.status);
      busy.reconstruction = reconstructionBusy(snap.reconstruction?.status);
      busy.colmap = colmapBusy(snap.colmap?.status);

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
      busy.report = reportBusy(ev.status);
      queryClient.setQueryData(["report-process", reportId], (prev: any) => {
        const base = prev ?? queryClient.getQueryData(["report", reportId]);
        if (!base) return undefined;
        return { ...base, ...defined({ status: ev.status, progress: ev.progress }) };
      });
    };

    const onColmapStatus = (e: MessageEvent) => {
      const ev = parse(e);
      if (!ev) return;
      busy.colmap = colmapBusy(ev.status);
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
      busy.detection = detectionBusy(ev.status);
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
      busy.description = descriptionBusy(ev.status);
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
      busy.reconstruction = reconstructionBusy(ev.status);
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

    // ── connection lifecycle ────────────────────────────────────────────────

    const clearTimer = (t: ReturnType<typeof setTimeout> | null) => {
      if (t) clearTimeout(t);
      return null;
    };

    /** Drop the socket without touching the phase (callers decide what's next). */
    const closeStream = () => {
      failTimer = clearTimer(failTimer);
      idleTimer = clearTimer(idleTimer);
      es?.close();
      es = null;
    };

    /**
     * Decide whether the connection is still earning its socket. Called after
     * every event: busy cancels a pending release, quiet arms one.
     */
    const reassess = () => {
      if (disposed || !es) return;
      if (anythingBusy()) {
        // Once we have seen real work, keep the socket a while after it stops
        // so follow-up jobs (COLMAP after mapping) are caught without a reconnect.
        graceMs = ACTIVE_GRACE_MS;
        idleTimer = clearTimer(idleTimer);
        return;
      }
      // Arm once — the grace window starts when things went quiet, not on every
      // unrelated event (map_created keeps arriving after a run completes).
      if (idleTimer) return;
      idleTimer = setTimeout(() => {
        idleTimer = null;
        if (disposed || anythingBusy()) return;
        closeStream();
        setPhase("idle");
        scheduleHeartbeat();
      }, graceMs);
    };

    /** While idle: re-snapshot occasionally so runs started elsewhere show up. */
    const scheduleHeartbeat = () => {
      heartbeatTimer = clearTimer(heartbeatTimer);
      heartbeatTimer = setTimeout(() => {
        heartbeatTimer = null;
        connect();
      }, HEARTBEAT_MS);
    };

    const scheduleRetry = () => {
      if (disposed || retryTimer) return;
      retryTimer = setTimeout(() => {
        retryTimer = null;
        connect();
      }, RETRY_AFTER_MS);
    };

    const connect = () => {
      if (disposed || es) return;
      heartbeatTimer = clearTimer(heartbeatTimer);
      es = new EventSource(getReportEventsUrl(reportId));

      es.onopen = () => {
        failTimer = clearTimer(failTimer);
        setPhase("streaming");
      };

      es.onerror = () => {
        // EventSource retries on its own; only give up (and let polling take
        // over) when it can't reopen within FAIL_AFTER_MS.
        if (!failTimer) {
          failTimer = setTimeout(() => {
            failTimer = null;
            closeStream();
            setPhase("fallback");
            scheduleRetry();
          }, FAIL_AFTER_MS);
        }
      };

      // Every handler updates `busy`; reassess right after so a stream that has
      // nothing left to report releases its socket.
      const on = (type: string, handler: (e: MessageEvent) => void) => {
        es!.addEventListener(type, (e) => {
          handler(e as MessageEvent);
          reassess();
        });
      };

      on("snapshot", onSnapshot);
      on("report_status", onReportStatus);
      on("colmap_status", onColmapStatus);
      on("detection_status", onDetectionStatus);
      on("description_status", onDescriptionStatus);
      on("reconstruction_status", onReconstructionStatus);
      on("map_created", onMapCreated);
      on("detections_added", onDetectionsAdded);
    };

    // A job was just started from this tab: reconnect now and hold the socket
    // for the full grace window even if Redis has not flipped the status yet.
    wakeRef.current = () => {
      if (disposed) return;
      graceMs = ACTIVE_GRACE_MS;
      idleTimer = clearTimer(idleTimer);
      heartbeatTimer = clearTimer(heartbeatTimer);
      retryTimer = clearTimer(retryTimer);
      connect();
    };

    // Coming back to a backgrounded tab: pull a fresh snapshot immediately
    // instead of waiting out the heartbeat.
    const onVisibility = () => {
      if (disposed || document.visibilityState !== "visible" || es) return;
      connect();
    };
    document.addEventListener("visibilitychange", onVisibility);

    connect();

    return () => {
      disposed = true;
      document.removeEventListener("visibilitychange", onVisibility);
      wakeRef.current = () => {};
      retryTimer = clearTimer(retryTimer);
      heartbeatTimer = clearTimer(heartbeatTimer);
      closeStream();
      setPhase("connecting");
    };
  }, [reportId, queryClient]);

  return useMemo(
    () => ({
      streaming: phase === "streaming",
      // "idle" is a healthy state — SSE owns the updates, it just isn't holding
      // a socket for a report where nothing is happening.
      suspendPolling: phase === "streaming" || phase === "idle",
      wake,
    }),
    [phase, wake]
  );
}
