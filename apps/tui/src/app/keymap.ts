import type { KeyEvent } from "@opentui/core";

export const RESERVED_CTRL_KEYS = new Set([
  "c", // SIGINT / quit
  "s", // XOFF / terminal flow control
  "q", // XON / terminal flow control
  "z", // suspend
  "w", // common terminal/browser close-tab binding
  "t", // common terminal/browser new-tab binding
]);

function hasOnlyCtrlModifier(key: KeyEvent): boolean {
  return Boolean(key.ctrl && !key.meta && !key.option && !key.super);
}

function hasNoCommandModifiers(key: KeyEvent): boolean {
  return Boolean(!key.ctrl && !key.meta && !key.option && !key.super);
}

export function isCtrlKey(key: KeyEvent, name: string): boolean {
  return hasOnlyCtrlModifier(key) && key.name === name;
}

export function isCtrlSpace(key: KeyEvent): boolean {
  return (
    hasOnlyCtrlModifier(key)
    && key.name === "space"
    && (key.sequence === "\u0000" || key.raw === "\u0000")
  );
}

export function ctrlDigitIndex(key: KeyEvent): number | null {
  if (!hasOnlyCtrlModifier(key) || !/^[1-9]$/.test(key.name)) {
    return null;
  }
  return Number.parseInt(key.name, 10) - 1;
}

function normalizedKeyName(key: KeyEvent): string {
  return (key.name || "").toLowerCase().replace(/[\s_-]/g, "");
}

export function tabDirection(key: KeyEvent): 1 | -1 | null {
  if (!hasNoCommandModifiers(key)) {
    return null;
  }
  if (key.sequence === "\u001b[Z" || key.raw === "\u001b[Z") {
    return -1;
  }
  const normalizedName = normalizedKeyName(key);
  if (normalizedName === "backtab" || normalizedName === "shifttab") {
    return -1;
  }
  if (normalizedName === "tab") {
    return key.shift ? -1 : 1;
  }
  return null;
}

export type ScrollPageKey = "pageup" | "pagedown" | "home" | "end";

export function scrollPageKey(key: KeyEvent): ScrollPageKey | null {
  if (key.meta || key.option || key.super) {
    return null;
  }
  const normalizedName = normalizedKeyName(key);
  if (["pageup", "pagedown", "home", "end"].includes(normalizedName)) {
    return normalizedName as ScrollPageKey;
  }
  return null;
}

export function ctrlLineScrollDirection(key: KeyEvent): -1 | 1 | null {
  if (!hasOnlyCtrlModifier(key)) {
    return null;
  }
  const normalizedName = normalizedKeyName(key);
  if (normalizedName === "up") {
    return -1;
  }
  if (normalizedName === "down") {
    return 1;
  }
  return null;
}

export function consumeKey(key: KeyEvent): void {
  key.preventDefault();
  key.stopPropagation();
}

export function globalShortcutHelp(): string {
  return [
    "Ctrl+G nav/type",
    "Ctrl+Space create",
    "Ctrl+B body",
    "Ctrl+F field/repo",
    "Ctrl+K actions/help",
    "Ctrl+L logs",
    "Ctrl+R refresh",
    "Ctrl+. cancel",
    "Ctrl+1..9 pages",
    "Tab/Shift+Tab pages",
    "? help",
  ].join("  ");
}
