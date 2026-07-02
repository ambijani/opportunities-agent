import { verifyDiscordSignature } from "./verify";
import { handleSubscribe, handleSubscribeSelect } from "./commands/subscribe";
import { handleUnsubscribe } from "./commands/unsubscribe";
import { handleAddJob, handleAddJobChannelSelect, handleAddJobModalSubmit } from "./commands/add_job";

export interface Env {
  DISCORD_PUBLIC_KEY:    string;
  DISCORD_BOT_TOKEN:     string;
  DISCORD_APPLICATION_ID: string;
  TURSO_DATABASE_URL:    string;
  TURSO_AUTH_TOKEN:      string;
  CHANNEL_OPTIONS_JSON:  string;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    // Discord requires Ed25519 signature verification on every request
    const isValid = await verifyDiscordSignature(request, env.DISCORD_PUBLIC_KEY);
    if (!isValid) {
      return new Response("Unauthorized", { status: 401 });
    }

    const body = await request.json() as Record<string, unknown>;
    const type = body.type as number;

    // type 1 = PING (Discord endpoint verification)
    if (type === 1) {
      return Response.json({ type: 1 });
    }

    // type 2 = APPLICATION_COMMAND
    if (type === 2) {
      const commandName = ((body.data as Record<string, unknown>)?.name as string) ?? "";
      switch (commandName) {
        case "subscribe":   return handleSubscribe(body, env);
        case "unsubscribe": return handleUnsubscribe(body, env);
        case "add-job":     return handleAddJob(body, env);
        default:
          return new Response("Unknown command", { status: 400 });
      }
    }

    // type 3 = MESSAGE_COMPONENT (button / select)
    if (type === 3) {
      const customId = ((body.data as Record<string, unknown>)?.custom_id as string) ?? "";
      if (customId === "subscribe_select")       return handleSubscribeSelect(body, env);
      if (customId === "add_job_channel_select") return handleAddJobChannelSelect(body, env);
      return new Response("Unknown component", { status: 400 });
    }

    // type 5 = MODAL_SUBMIT
    if (type === 5) {
      const customId = ((body.data as Record<string, unknown>)?.custom_id as string) ?? "";
      if (customId.startsWith("add_job_modal:")) {
        return handleAddJobModalSubmit(body, env, ctx);
      }
      return new Response("Unknown modal", { status: 400 });
    }

    return new Response("Unknown interaction type", { status: 400 });
  },
};
