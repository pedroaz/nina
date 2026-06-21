import { runTui } from "./app/shell";

runTui().catch((err) => {
  console.error("TUI error:", err);
  process.exit(1);
});
