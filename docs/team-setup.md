# Touchstone — teammate setup (~5 minutes)

Touchstone gives Claude a shared memory of our team's brand voice and process.
Once it's set up, Claude checks our shared notes before helping with marketing work,
and saves anything new it learns so the rest of us get it too.

You'll need two things from Charlie:
- **Your personal key** (sent to you privately) — looks like `b096c226-4e6a-...`
- The server URL: `https://web-production-18aa.up.railway.app/mcp`

---

## 1. Connect Touchstone to Claude

### Claude Desktop (recommended)

1. Open **Claude → Settings → Developer → Edit Config**
   (this opens a file called `claude_desktop_config.json`).
2. Paste this in. If the file already has an `mcpServers` block, add `team-memory` inside it.
   **Replace `PASTE-YOUR-KEY-HERE` with the key Charlie sent you.**

   ```json
   {
     "mcpServers": {
       "team-memory": {
         "url": "https://web-production-18aa.up.railway.app/mcp",
         "headers": { "Authorization": "Bearer PASTE-YOUR-KEY-HERE" }
       }
     }
   }
   ```

3. Save the file, then **fully quit Claude and reopen it** (not just close the window).
4. You should now see **team-memory** listed under connectors/tools, with `recall` and
   `store`. Approve/enable it if Claude asks.

### Claude.ai (web)

1. **Settings → Connectors → Add custom connector.**
2. Paste the URL above and your key as the Bearer token.
3. If the web form doesn't have a place to enter a token/header, use **Claude Desktop**
   instead (above) — it's the reliable path for our key-based setup.

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

## Troubleshooting

- **Tools don't appear** → fully quit and reopen Claude Desktop; double-check the JSON is
  valid (no trailing commas, matching braces).
- **"Unauthorized" / 401** → the key is wrong or has an extra space. Re-copy it exactly
  from Charlie's message (no quotes, no spaces).
- **Nothing gets recalled** → make sure the instructions from step 2 are in your Project,
  and that you're chatting inside that Project.
- **Still stuck** → ping Charlie; he can check the admin dashboard and re-issue your key.
