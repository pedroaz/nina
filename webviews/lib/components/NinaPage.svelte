<script lang="ts"></script>

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
