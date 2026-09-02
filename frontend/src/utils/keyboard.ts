/**
 * True when a keystroke belongs to a text field and must not trigger a shortcut.
 *
 * Pass the event's target where one is available; falls back to the focused element
 * for handlers that only see the key.
 */
export function isTypingTarget(target?: EventTarget | null): boolean {
  const el = (target as HTMLElement | null) ?? (document.activeElement as HTMLElement | null);
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
}
