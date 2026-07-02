import type { Env } from "../index";
import { removeSubscriber } from "../db";

export async function handleUnsubscribe(interaction: Record<string, unknown>, env: Env): Promise<Response> {
  const user = (interaction.member as Record<string, unknown>)?.user ?? interaction.user;
  const userId = (user as Record<string, string>)?.id;

  const removed = userId ? await removeSubscriber(userId, env) : false;

  return Response.json({
    type: 4,
    data: {
      flags: 64,
      content: removed
        ? "You've been unsubscribed and won't receive any more DMs."
        : "You weren't subscribed. Use `/subscribe` to opt in.",
    },
  });
}
