<script lang="ts">
  import { Handle, Position, type NodeProps } from "@xyflow/svelte";
  import type { Writable } from "svelte/store";

  export let data: { label: string; filePath: string };

  type $$Props = NodeProps;

  const { label, filePath } = data;
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:dblclick={() => {
    tsvscode.postMessage({
      command: "open-file",
      data: { filePath: filePath },
    });
  }}
>
  <div class="container">
    {label}
  </div>
</div>

<style>
  .container {
    background-color: white;
    border: 1px solid black;
    color: black;
    border-radius: 5px;
    padding: 10px;
    width: 200px;
    height: 100px;
    display: flex;
    justify-content: center;
    align-items: center;
  }
</style>
