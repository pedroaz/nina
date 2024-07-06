<script lang="ts">
  import { SvelteFlow, Background } from "@xyflow/svelte";
  import { nodes, edges } from "../stores/NinaStore";
  import "@xyflow/svelte/dist/style.css";
  import { NodeManager } from "../services/NodeManager";
  import { onMount } from "svelte";
  import { getFileName } from "../services/Utils";
  import { get } from "svelte/store";

  import FileNode from "../components/Nodes/FileNodes.svelte";
  import { sendMessage } from "../services/MessageSender";
  import type { NinaState } from "../services/Models";

  const nodeTypes = {
    file: FileNode,
  };

  onMount(() => {
    window.addEventListener("message", (event) => {
      const message = event.data;
      switch (message.command) {
        case "add-file":
          var filename = getFileName(message.data.path);
          NodeManager.createNode(filename, message.data.path);
          break;
        case "render-state":
          console.log("render-state", message.data);
          nodes.set(message.data.nodes);
          edges.set(message.data.edges);
          break;
      }
    });
  });

  function handleButtonClick() {
    const state: NinaState = { nodes: get(nodes), edges: get(edges) };
    console.log("Saving State", state);
    sendMessage("persist-state", state);
  }
</script>

<main>
  <SvelteFlow {nodes} {edges} fitView {nodeTypes}>
    <Background bgColor="rgba(126,159,219,0.5)" />
  </SvelteFlow>
  <button
    on:click={handleButtonClick}
    style="position: fixed; bottom: 50px; right: 50px; height:50px; width: 100px"
    >Save</button
  >
</main>

<style>
  main {
    height: 100vh;
  }
</style>
