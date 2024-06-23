<script lang="ts">
  import { SvelteFlow, Background } from "@xyflow/svelte";
  import { nodes, edges } from "../stores/NinaStore";
  import "@xyflow/svelte/dist/style.css";
  import { NodeManager } from "../services/NodeManager";
  import { onMount } from "svelte";
  import { getFileName } from "../services/Utils";

  import FileNode from "../components/Nodes/FileNodes.svelte";

  const nodeTypes = {
    file: FileNode,
  };

  onMount(() => {
    window.addEventListener("message", (event) => {
      const message = event.data;
      switch (message.command) {
        case "addFile":
          var filename = getFileName(message.data.path);
          NodeManager.createNode(filename, message.data.path);
          break;
      }
    });
  });
</script>

<main>
  <SvelteFlow {nodes} {edges} fitView {nodeTypes}>
    <Background bgColor="rgba(126,159,219,0.5)" />
  </SvelteFlow>
</main>

<style>
  main {
    height: 100vh;
  }
</style>
