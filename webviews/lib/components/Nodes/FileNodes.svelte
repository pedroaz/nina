<script lang="ts">
  import { Handle, Position, type NodeProps } from "@xyflow/svelte";
  import { sendMessage } from "../../services/MessageSender";

  export let data: { label: string; filePath: string };

  type $$Props = NodeProps;

  const { label, filePath } = data;
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:dblclick={() => {
    sendMessage("open-file", { filePath: filePath });
  }}
>
  <div class="container">
    {label}
    <Handle type="source" position={Position.Top} id="a" class="handle" />
    <Handle type="source" position={Position.Right} id="b" class="handle" />
    <Handle type="source" position={Position.Bottom} id="c" class="handle" />
    <Handle type="source" position={Position.Left} id="d" class="handle" />
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
