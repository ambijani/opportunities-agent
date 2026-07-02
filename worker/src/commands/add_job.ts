import type { Env } from "../index";
import { hasBeenPosted, markPosted, getSubscribersForChannel } from "../db";
import { postToChannel, sendFollowup, dmUser, validateUrl } from "../discord";
import { buildEmbed } from "../embeds";
import { channelOptions } from "./subscribe";

export async function handleAddJob(interaction: Record<string, unknown>, env: Env): Promise<Response> {
  const options = channelOptions(env);
  return Response.json({
    type: 4,
    data: {
      flags: 64,
      content: "Where should this be posted?",
      components: [
        {
          type: 1,
          components: [
            {
              type: 3,
              custom_id: "add_job_channel_select",
              placeholder: "Pick a channel to post in...",
              min_values: 1,
              max_values: 1,
              options,
            },
          ],
        },
      ],
    },
  });
}

export async function handleAddJobChannelSelect(
  interaction: Record<string, unknown>,
  env: Env
): Promise<Response> {
  const values = ((interaction.data as Record<string, unknown>)?.values as string[]) ?? [];
  const selected = values[0]; // "jobType|category|channelId"

  return Response.json({
    type: 9, // MODAL
    data: {
      custom_id: `add_job_modal:${selected}`,
      title: "Add Opportunity",
      components: [
        modalRow("url",         "URL",                    "https://...",                           false),
        modalRow("job_title",   "Title",                  "Software Engineer Intern",              false),
        modalRow("company",     "Company",                "Acme Corp",                             false),
        modalRow("location",    "Location (optional)",    "Remote / New York, NY",                true),
        modalRow("description", "Description (optional)", "Brief description of the role...",     true, true),
      ],
    },
  });
}

export async function handleAddJobModalSubmit(
  interaction: Record<string, unknown>,
  env: Env,
  ctx: ExecutionContext
): Promise<Response> {
  const customId = (interaction.data as Record<string, unknown>)?.custom_id as string;
  const [, jobType, category, channelId] = customId.split(":");
  const appId = env.DISCORD_APPLICATION_ID;
  const token = interaction.token as string;

  const components = (interaction.data as Record<string, unknown>)?.components as unknown[];
  const url         = getModalValue(components, "url");
  const title       = getModalValue(components, "job_title");
  const company     = getModalValue(components, "company");
  const location    = getModalValue(components, "location") || "Not specified";
  const description = getModalValue(components, "description") || "";

  // Respond immediately with a deferred ephemeral so Discord doesn't timeout
  const deferred = Response.json({ type: 5, data: { flags: 64 } });

  // Do the real work asynchronously after we've returned the response
  ctx.waitUntil(
    (async () => {
      try {
        // 1. Dedup check
        if (await hasBeenPosted(url, env)) {
          await sendFollowup(appId, token, { content: "This URL has already been posted.", flags: 64 }, env);
          return;
        }

        // 2. URL validation
        if (!(await validateUrl(url))) {
          await sendFollowup(appId, token, { content: "URL check failed — verify the link and try again.", flags: 64 }, env);
          return;
        }

        // 3. Build embed and post to channel
        const embed = buildEmbed({
          title,
          company,
          location,
          description,
          url,
          jobType,
          category,
          source: "manual",
          datePosted: new Date().toISOString().split("T")[0],
        });

        const posted = await postToChannel(channelId, { embeds: [embed] }, env);
        if (!posted) {
          await sendFollowup(appId, token, { content: "Failed to post — check bot permissions in the target channel.", flags: 64 }, env);
          return;
        }

        // 4. Mark as posted in Turso
        const jobId = await sha256hex(url);
        await markPosted({ url, id: jobId.slice(0, 16), title, company, jobType, category, source: "manual" }, channelId, env);

        // 5. Confirm to user
        await sendFollowup(appId, token, {
          content: `Posted **${title}** at **${company}** → <#${channelId}>.`,
          flags: 64,
        }, env);

        // 6. DM subscribers
        const subscribers = await getSubscribersForChannel(channelId, env);
        for (const userId of subscribers) {
          await dmUser(userId, embed, env);
        }
      } catch (err) {
        console.error("add_job modal submit error:", err);
        await sendFollowup(appId, token, { content: "Something went wrong. Check the bot logs.", flags: 64 }, env);
      }
    })()
  );

  return deferred;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function modalRow(
  customId: string,
  label: string,
  placeholder: string,
  required: boolean,
  paragraph = false
): unknown {
  return {
    type: 1,
    components: [
      {
        type: 4, // TEXT_INPUT
        custom_id: customId,
        label,
        style: paragraph ? 2 : 1,
        placeholder,
        required: !required,
        max_length: customId === "description" ? 300 : 200,
      },
    ],
  };
}

function getModalValue(components: unknown[], customId: string): string {
  for (const row of components) {
    const items = ((row as Record<string, unknown>).components as Record<string, unknown>[]) ?? [];
    for (const item of items) {
      if (item.custom_id === customId) return String(item.value ?? "").trim();
    }
  }
  return "";
}

async function sha256hex(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const buf = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
