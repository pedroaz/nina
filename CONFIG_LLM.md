# LLM Configuration

1. Log in with the Codex CLI once on this machine:

   ```bash
   codex login
   ```

2. Tell Nina to use the Codex-backed OpenAI provider:

   ```bash
   nina config llm-provider openai
   ```

3. Pick the model you want Nina to use:

   ```bash
   nina config llm-model gpt-5.4-mini
   ```

4. Restart the daemon if it is already running:

   ```bash
   nina daemon restart
   ```

If your Codex auth file lives somewhere else, set `CODEX_AUTH_FILE` before starting Nina.

5. Test the LLM path:

   ```bash
   nina llm test "Reply with auth ok" --model gpt-5.4-mini
   ```

   The command prints the provider, model, and response.
