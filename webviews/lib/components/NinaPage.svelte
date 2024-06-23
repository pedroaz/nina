<script lang="ts">
  import { onMount } from "svelte";
  import { Node, Svelvet, Minimap, Controls, Group } from "svelvet";

  onMount(() => {
    window.addEventListener("message", (event) => {
      const message = event.data; // The json data that the extension sent
      switch (message.command) {
        case "addFile":
          console.log(message.data);
          break;
      }
    });
  });
</script>

<div style="border: red 1px solid;">
  <Svelvet theme="light" controls>
    <Node id="alpha" bgColor="red" label="Default Node" borderColor="white" />
  </Svelvet>
</div>

<!-- <button
  on:click={() => {
    console.log("click");
    tsvscode.postMessage({
      command: "alert",
      text: "🐛  on line ",
    });
  }}>My Btn</button
> -->
