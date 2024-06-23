import { nodes, edges } from "../stores/NinaStore";

export class NodeManager {
  public static createNode(label: string) {
    nodes.update((n) => [
      ...n,
      {
        id: `${n.length + 1}`,
        position: { x: 200, y: 200 },
        data: { label: label },
      },
    ]);
  }
}
