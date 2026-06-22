# LLM Configuration

Nina's AI path uses the local Codex CLI. Nina does not read API key environment variables or Codex auth token files directly.

1. Log in with the Codex CLI once on this machine:

   ```bash
   codex login
   ```

2. Configure Nina to use Codex CLI. Use `codex-cli` to let Codex pick its default model, or set an explicit Codex model such as `gpt-5.5`:

   ```bash
   nina config llm-provider codex
   nina config llm-model gpt-5.5
   nina config research-provider codex
   nina config research-model gpt-5.5
   nina config research-search-mode live
   ```

3. Restart the daemon if it is already running:

   ```bash
   nina daemon restart
   ```

4. Test the LLM and research paths:

   ```bash
   nina llm test "Reply with auth ok"
   nina research run "modern mobile authentication patterns"
   make smoke-research
   ```

   The LLM command prints `Provider: codex` when the request is handled through the CLI. Research uses Codex live web search by default and writes a `Research/<date> - <topic>.md` note into the vault. `make smoke-research` runs the same path through the daemon and CLI, then verifies the note exists and includes sources.
