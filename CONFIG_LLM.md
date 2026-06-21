# LLM Configuration

Nina's AI path uses the local Codex CLI. Nina does not read API key environment variables or Codex auth token files directly.

1. Log in with the Codex CLI once on this machine:

   ```bash
   codex login
   ```

2. Configure Nina to use Codex CLI:

   ```bash
   nina config llm-provider codex
   nina config research-provider codex
   ```

3. Restart the daemon if it is already running:

   ```bash
   nina daemon restart
   ```

4. Test the LLM path:

   ```bash
   nina llm test "Reply with auth ok"
   ```

   The command prints `Provider: codex` when the request is handled through the CLI.
