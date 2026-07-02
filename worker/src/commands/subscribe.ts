import type { Env } from "../index";
import { getSubscriberChannels, setSubscriberChannels } from "../db";

export function channelOptions(env: Env): { label: string; value: string }[] {
  try {
    return JSON.parse(env.CHANNEL_OPTIONS_JSON);
  } catch {
    return [];
  }
}

export async function handleSubscribe(interaction: Record<string, unknown>, env: Env): Promise<Response> {
  const user = (interaction.member as Record<string, unknown>)?.user ?? interaction.user;
  const userId = (user as Record<string, string>)?.id;

  const existing = userId ? await getSubscriberChannels(userId, env) : [];
  const options = channelOptions(env);

  const optionsWithDefaults = options.map((opt) => ({
    ...opt,
    default: existing.includes(opt.value.split("|")[2]),
  }));

  return Response.json({
    type: 4,
    data: {
      flags: 64,
      content: "Pick the channels you want DMs for (select all that apply):",
      components: [
        {
          type: 1,
          components: [
            {
              type: 3,
              custom_id: "subscribe_select",
              placeholder: "Select channels...",
              min_values: 1,
              max_values: options.length,
              options: optionsWithDefaults,
            },
          ],
        },
      ],
    },
  });
}

export async function handleSubscribeSelect(interaction: Record<string, unknown>, env: Env): Promise<Response> {
  const user = (interaction.member as Record<string, unknown>)?.user ?? interaction.user;
  const userId = (user as Record<string, string>)?.id;
  const values = ((interaction.data as Record<string, unknown>)?.values as string[]) ?? [];

  // values are "jobType|category|channelId" — extract unique channel IDs
  const channelIds = [...new Set(values.map((v) => v.split("|")[2]))];

  if (userId) await setSubscriberChannels(userId, channelIds, env);

  const options = channelOptions(env);
  const selectedLabels = options
    .filter((o) => values.includes(o.value))
    .map((o) => `• ${o.label}`)
    .join("\n");

  return Response.json({
    type: 7, // UPDATE_MESSAGE
    data: {
      flags: 64,
      content: `Subscribed! You'll get DMs for:\n${selectedLabels}\n\nRun \`/subscribe\` again to change, or \`/unsubscribe\` to opt out.`,
      components: [],
    },
  });
}
