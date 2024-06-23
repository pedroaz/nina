<script lang="ts">
  import { Handle, Position, type NodeProps } from "@xyflow/svelte";
  import type { Writable } from "svelte/store";

  export let data: { color: Writable<string>; label: string };
  type $$Props = NodeProps;

  const { color, label } = data;
</script>

<div>
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
