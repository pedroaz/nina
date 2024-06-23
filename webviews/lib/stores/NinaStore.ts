import { writable } from "svelte/store";

export const nodes = writable([
  {
    id: "1", // required and needs to be a string
    position: { x: 0, y: 0 }, // required
    data: { label: "hey" }, // required
  },
  {
    id: "2",
    position: { x: 100, y: 100 },
    data: { label: "world" },
  },
]);

export const edges = writable([{ id: "1-2", source: "1", target: "2" }]);
