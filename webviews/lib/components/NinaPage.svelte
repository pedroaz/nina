<script lang="ts">
  import { onMount } from "svelte";

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

<h1>Hello from Pedro2</h1>

<button
  on:click={() => {
    console.log("click");
    tsvscode.postMessage({
      command: "alert",
      text: "🐛  on line ",
    });
  }}>My Btn</button
>
