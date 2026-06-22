import { describe, expect, test } from "bun:test";
import type { KeyEvent } from "@opentui/core";
import { RESERVED_CTRL_KEYS, ctrlDigitIndex, ctrlLineScrollDirection, isCtrlKey, isCtrlSpace, scrollPageKey, tabDirection } from "./keymap";

function key(name: string, overrides: Partial<KeyEvent> = {}): KeyEvent {
  return {
    name,
    ctrl: false,
    meta: false,
    option: false,
    super: false,
    shift: false,
    sequence: name,
    raw: name,
    eventType: "press",
    preventDefault() {},
    stopPropagation() {},
    ...overrides,
  } as KeyEvent;
}

describe("TUI keymap", () => {
  test("ctrl digit shortcuts resolve to zero-based page indexes", () => {
    expect(ctrlDigitIndex(key("1", { ctrl: true }))).toBe(0);
    expect(ctrlDigitIndex(key("9", { ctrl: true }))).toBe(8);
    expect(ctrlDigitIndex(key("0", { ctrl: true }))).toBeNull();
  });

  test("ctrl helpers reject additional modifiers", () => {
    expect(isCtrlKey(key("g", { ctrl: true }), "g")).toBe(true);
    expect(isCtrlKey(key("g", { ctrl: true, shift: true }), "g")).toBe(true);
    expect(isCtrlKey(key("g", { ctrl: true, meta: true }), "g")).toBe(false);
  });

  test("ctrl space accepts OpenTUI NUL key events", () => {
    expect(isCtrlSpace(key("space", { ctrl: true, sequence: "\u0000", raw: "\u0000" }))).toBe(true);
    expect(isCtrlSpace(key("space", { ctrl: true, sequence: "space", raw: "space" }))).toBe(false);
    expect(isCtrlSpace(key("space"))).toBe(false);
    expect(isCtrlSpace(key("space", { ctrl: true, meta: true, sequence: "\u0000", raw: "\u0000" }))).toBe(false);
  });

  test("tab direction normalizes forward and backward tab variants", () => {
    expect(tabDirection(key("tab"))).toBe(1);
    expect(tabDirection(key("tab", { shift: true }))).toBe(-1);
    expect(tabDirection(key("backtab"))).toBe(-1);
    expect(tabDirection(key("shift-tab"))).toBe(-1);
    expect(tabDirection(key("tab", { sequence: "\u001b[Z", raw: "\u001b[Z" }))).toBe(-1);
    expect(tabDirection(key("tab", { ctrl: true }))).toBeNull();
  });

  test("scroll page keys normalize terminal variants", () => {
    expect(scrollPageKey(key("pageup"))).toBe("pageup");
    expect(scrollPageKey(key("page-up"))).toBe("pageup");
    expect(scrollPageKey(key("page_down"))).toBe("pagedown");
    expect(scrollPageKey(key("Home"))).toBe("home");
    expect(scrollPageKey(key("end", { meta: true }))).toBeNull();
  });

  test("ctrl up and down map to line scroll directions", () => {
    expect(ctrlLineScrollDirection(key("up", { ctrl: true }))).toBe(-1);
    expect(ctrlLineScrollDirection(key("down", { ctrl: true }))).toBe(1);
    expect(ctrlLineScrollDirection(key("down"))).toBeNull();
    expect(ctrlLineScrollDirection(key("down", { ctrl: true, meta: true }))).toBeNull();
  });

  test("reserved ctrl letters document terminal conflicts", () => {
    expect(RESERVED_CTRL_KEYS.has("w")).toBe(true);
    expect(RESERVED_CTRL_KEYS.has("t")).toBe(true);
    expect(RESERVED_CTRL_KEYS.has("s")).toBe(true);
    expect(RESERVED_CTRL_KEYS.has("q")).toBe(true);
    expect(RESERVED_CTRL_KEYS.has("d")).toBe(false);
  });
});
