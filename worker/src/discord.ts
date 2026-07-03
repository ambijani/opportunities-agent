import type { Env } from "./index";

const DISCORD_API = "https://discord.com/api/v10";

async function discordRequest(
  method: string,
  path: string,
  body: unknown,
  env: Env
): Promise<Response> {
  return fetch(`${DISCORD_API}${path}`, {
    method,
    headers: {
      Authorization: `Bot ${env.DISCORD_BOT_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export async function postToChannel(
  channelId: string,
  payload: { content?: string; embeds?: unknown[] },
  env: Env
): Promise<boolean> {
  const resp = await discordRequest("POST", `/channels/${channelId}/messages`, payload, env);
  return resp.ok;
}

export async function sendFollowup(
  appId: string,
  token: string,
  payload: { content?: string; embeds?: unknown[]; flags?: number },
  env: Env
): Promise<void> {
  await fetch(`${DISCORD_API}/webhooks/${appId}/${token}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function dmUser(userId: string, embed: unknown, env: Env): Promise<void> {
  // Open DM channel
  const dmResp = await discordRequest("POST", "/users/@me/channels", { recipient_id: userId }, env);
  if (!dmResp.ok) return;
  const dmChannel = await dmResp.json() as { id: string };

  // Send DM
  await discordRequest(
    "POST",
    `/channels/${dmChannel.id}/messages`,
    { content: "📌 A new curated opportunity was just posted:", embeds: [embed] },
    env
  );
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Some startups don't have an apply link — they just list a contact email. */
export function isEmail(value: string): boolean {
  return EMAIL_RE.test(value.replace(/^mailto:/i, ""));
}

/** Validate a "url", which may instead be a plain email address or mailto: link. */
export async function validateUrl(url: string): Promise<boolean> {
  if (isEmail(url)) return true;
  try {
    const resp = await fetch(url, { method: "HEAD", redirect: "follow" });
    return resp.status < 500;
  } catch {
    return false;
  }
}

export function ephemerealJson(content: string): Response {
  return Response.json({ type: 4, data: { flags: 64, content } });
}

export function deferEphemeral(): Response {
  return Response.json({ type: 5, data: { flags: 64 } });
}
