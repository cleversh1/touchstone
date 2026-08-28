# Connect the Vercel Slack agent to Touchstone

Touchstone exposes one purpose-built, read-only MCP tool for the Slack reviewer:

```text
list_active_rules(platform, post_type?)
```

The Slack service must call it once at the start of every review. Store the
returned `rule_set_version` with the review record. Do **not** call `recall()`
for rule enforcement: recall is semantic top-k retrieval and may omit an active
rule. Do **not** expose `store()` or `deprecate_rule()` to the language model.

## 1. Create a read-only service key

Run this from a machine that has `DATABASE_URL` for the Touchstone database:

```bash
python manage.py create-key --name "Vercel Touchstone reviewer" --scopes rules:read
```

Copy the key when it is printed. It is shown only once. Add it in the Vercel
project settings as `TOUCHSTONE_MCP_TOKEN`, and add the following value as
`TOUCHSTONE_MCP_URL`:

```text
https://web-production-18aa.up.railway.app/mcp
```

Never put this key in a client-side environment variable, Slack message, Git
commit, or model prompt. A rules-read key cannot write or delete observations.

## 2. Install the MCP client in the Vercel project

```bash
pnpm add ai @ai-sdk/mcp @modelcontextprotocol/sdk zod
```

## 3. Add a server-only rule loader

Create `lib/touchstone-rules.ts` in the Vercel project:

```ts
import { createMCPClient } from '@ai-sdk/mcp';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { z } from 'zod';

const platformSchema = z.enum(['announcements', 'linkedin', 'substack']);

const ruleResponseSchema = z.object({
  platform: platformSchema,
  post_type: z.string().nullable(),
  rule_set_version: z.string(),
  count: z.number(),
  rules: z.array(z.object({
    id: z.string(),
    text: z.string(),
    scope: z.string(),
    post_type: z.string().nullable(),
    kind: z.enum(['required', 'guidance', 'example']),
    rule_version: z.number(),
    source_summary: z.string(),
  })),
});

export async function loadTouchstoneRules(
  platform: z.infer<typeof platformSchema>,
  postType?: string,
) {
  const url = process.env.TOUCHSTONE_MCP_URL;
  const token = process.env.TOUCHSTONE_MCP_TOKEN;
  if (!url || !token) throw new Error('Touchstone MCP is not configured.');

  const client = await createMCPClient({
    transport: new StreamableHTTPClientTransport(new URL(url), {
      requestInit: { headers: { Authorization: `Bearer ${token}` } },
    }),
  });

  try {
    const tools = await client.tools({
      schemas: {
        list_active_rules: {
          inputSchema: z.object({ platform: platformSchema, post_type: z.string().optional() }),
          outputSchema: ruleResponseSchema,
        },
      },
    });

    return await tools.list_active_rules.execute(
      { platform, post_type: postType },
      { messages: [], toolCallId: 'touchstone-rules' },
    );
  } finally {
    await client.close();
  }
}
```

Call `loadTouchstoneRules()` in application code before the model call, not as a
tool the model may choose to call. Give the model only the resulting active rules
and never the Touchstone token.

## 4. Failure behaviour

If Touchstone is unavailable, post deterministic link-check results and state
that brand-rule suggestions were unavailable. Do not reuse a stale rule snapshot
unless the product explicitly implements and labels a cache with its version and
expiry.
