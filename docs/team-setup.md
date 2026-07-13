# Touchstone — teammate setup (~5 minutes)

Touchstone gives Claude a shared memory of our team's brand voice and process.
Once it's set up, Claude checks our shared notes before helping with marketing work,
and saves anything new it learns so the rest of us get it too.

**Two ways to use it — pick the one that fits your setup:**

- **Option A — Full setup (recommended).** Claude connects to Touchstone directly, so
  it recalls the rules automatically *and* saves new ones. Works in **Claude Desktop**
  or **Claude Code** (Claude.ai web isn't supported — see below). Steps 1–3 below.
- **Option B — Read-only link.** Can't add a connector (free plan, ChatGPT, or any other
  tool)? Open a link, copy the current rules, paste them into your chat. No login, no
  install. Jump to ["No connector?"](#no-connector-read-only-rules-link) at the bottom.

For **Option A** you'll need two things from Charlie:
- **Your personal key** (sent to you privately) — a UUID like `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`
- The server URL: `https://web-production-18aa.up.railway.app/mcp`

---

## 1. Connect Touchstone to Claude

Your key always goes in an `Authorization` header — never in the URL. And don't use
Settings → Connectors → **"Add custom connector"**: that flow requires OAuth, which our
static-key server doesn't support, so it will fail.

### Claude Desktop (recommended for most)

Requires Node.js (for the `mcp-remote` bridge — check with `node --version`; if missing,
install from <https://nodejs.org> or `brew install node`).

1. Open **Claude → Settings → Developer → Edit Config** (opens `claude_desktop_config.json`).
2. Add `team-memory` inside `mcpServers` (keep any servers already there).
   **Replace `PASTE-YOUR-KEY-HERE` with the key Charlie sent you.**

   ```json
   {
     "mcpServers": {
       "team-memory": {
         "command": "npx",
         "args": [
           "-y", "mcp-remote",
           "https://web-production-18aa.up.railway.app/mcp",
           "--header", "Authorization: Bearer PASTE-YOUR-KEY-HERE"
         ]
       }
     }
   }
   ```

3. Save, then **fully quit Claude and reopen it** (⌘Q — not just closing the window).
4. `team-memory` appears with `recall` / `store` / `delete`. First launch spawns
   `npx mcp-remote`, so give it a few seconds.

### Claude Code (CLI) — cleanest if you use it

Claude Code speaks to a header-authenticated remote server natively — no bridge, no OAuth.
One command (replace the key):

```bash
claude mcp add --transport http team-memory \
  https://web-production-18aa.up.railway.app/mcp \
  --header "Authorization: Bearer PASTE-YOUR-KEY-HERE" \
  --scope user
```

`--scope user` makes it available in every project (drop it to add only to the current
directory). Verify with `claude mcp list` — `team-memory` should show as connected.

### Claude.ai (web) — not supported

Web custom connectors are OAuth-only and won't accept a static Bearer key, so this setup
doesn't work there. Use Claude Desktop or Claude Code above — or, for read-only access,
the share link in ["No connector?"](#no-connector-read-only-rules-link) below.

---

## 2. Add the team instructions (one time)

Create or open a **Project** in Claude (Projects keep instructions persistent across
chats). Paste this into the project's **custom instructions**:

```
You have access to a shared team memory tool called Touchstone.

At the start of every task:
- Call recall() with a short description of what you're about to help with.
- If observations are returned, tell the user what you found before responding:
  "Based on your team's notes, I'm applying: [list]. Here's my response: ..."
- If nothing relevant is returned, proceed normally.

During and after every task:
- If the user corrects your tone, word choice, or structure — store that as a
  brand_voice observation.
- If the user describes a process step or workflow — store that as a process observation.
- If a decision is made (about strategy, messaging, audience, etc.) — store that as a
  decision observation.
- If you infer a convention from the user's edits or preferences — store it with a
  source_summary explaining what you observed.

Only store things that would be useful to a different team member doing a similar task.
Don't store ephemeral task details or content specific to one piece of work.
```

Do your marketing work inside that Project so the instructions always apply.

---

## 3. Test it

In a new chat (inside the Project), ask:

> "Recall our brand voice notes for a blog post intro."

Claude should call `recall` and show our V1 rules (banned words, formatting, length,
etc.). If you see those surfaced before its answer — you're all set. ✅

---

## No connector? Read-only rules link

If your plan or tool can't add a connector (free Claude, ChatGPT, or anything else),
you can still use the rules — just read-only.

1. Open the share link Charlie sends you: **`<SHARE_LINK>`**
   *(Charlie: this is `https://web-production-18aa.up.railway.app/rules/<SHARE_TOKEN>` —
   share it via Slack, not in the repo.)*
2. Click **Copy all (Markdown)**.
3. Paste it into your chat — either at the top of a new conversation, or into your
   ChatGPT/Claude custom instructions, e.g. "Follow these brand rules: [paste]".

The page always reflects the latest rules, so re-copy it whenever you start something new.

What you **don't** get this way: automatic recall, and saving new rules back to the team
(that needs the full connector setup above). Treat this as a quick reference, not a
replacement for Option A.

---

## Troubleshooting

- **Tools don't appear** → fully quit and reopen Claude Desktop; double-check the JSON is
  valid (no trailing commas, matching braces).
- **"Unauthorized" / 401** → the key is wrong or has an extra space. Re-copy it exactly
  from Charlie's message (no quotes, no spaces).
- **Nothing gets recalled** → make sure the instructions from step 2 are in your Project,
  and that you're chatting inside that Project.
- **Still stuck** → ping Charlie; he can check the admin dashboard and re-issue your key.
