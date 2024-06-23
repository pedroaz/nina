import type { Edge, Node } from "@xyflow/svelte";
import { writable } from "svelte/store";

export const nodes = writable([] as Array<Node>);

export const edges = writable([] as Array<Edge>);
