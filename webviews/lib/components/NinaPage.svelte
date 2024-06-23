<script lang="ts">
  import {
    SvelteFlow,
    Background,
    Controls,
    BackgroundVariant,
  } from "@xyflow/svelte";

  import { nodes, edges } from "../stores/NinaStore";

  import "@xyflow/svelte/dist/style.css";
  import { NodeManager } from "../services/NodeManager";

  // onMount(() => {
  //   window.addEventListener("message", (event) => {
  //     const message = event.data; // The json data that the extension sent
  //     switch (message.command) {
  //       case "addFile":
  //         console.log(message.data);
  //         break;
  //     }
  //   });
  // });
</script>

<main>
  <button
    on:click={() => {
      console.log("clicked");
      NodeManager.createNode("TEST");
    }}>Add New Node</button
  >
  <SvelteFlow {nodes} {edges} fitView>
    <Background bgColor="rgba(126,159,219,0.5)" patternColor="white" />
  </SvelteFlow>
</main>

<style>
  main {
    height: 100vh;
  }
</style>
