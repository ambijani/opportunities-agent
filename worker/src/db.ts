import { createClient } from "@libsql/client/web";
import type { Env } from "./index";

export function getDb(env: Env) {
  return createClient({
    url: env.TURSO_DATABASE_URL,
    authToken: env.TURSO_AUTH_TOKEN,
  });
}

export async function hasBeenPosted(url: string, env: Env): Promise<boolean> {
  const db = getDb(env);
  const hash = await sha256hex(url);
  const rs = await db.execute({ sql: "SELECT 1 FROM posted_jobs WHERE url_hash = ?", args: [hash] });
  return rs.rows.length > 0;
}

export async function markPosted(
  job: { url: string; id: string; title: string; company: string; jobType: string; category: string; source: string },
  channelId: string,
  env: Env
): Promise<void> {
  const db = getDb(env);
  const hash = await sha256hex(job.url);
  await db.execute({
    sql: "INSERT OR IGNORE INTO posted_jobs VALUES (?,?,?,?,?,?,?,?,?,?)",
    args: [hash, job.url, job.id, job.title, job.company, channelId, job.jobType, job.category, job.source, new Date().toISOString()],
  });
}

export async function getSubscribersForChannel(channelId: string, env: Env): Promise<string[]> {
  const db = getDb(env);
  const rs = await db.execute({ sql: "SELECT user_id FROM subscribers WHERE channel_id = ?", args: [channelId] });
  return rs.rows.map((r) => String(r[0]));
}

export async function setSubscriberChannels(userId: string, channelIds: string[], env: Env): Promise<void> {
  const db = getDb(env);
  const now = new Date().toISOString();
  await db.batch([
    { sql: "DELETE FROM subscribers WHERE user_id = ?", args: [userId] },
    ...channelIds.map((cid) => ({
      sql: "INSERT INTO subscribers VALUES (?,?,?)",
      args: [userId, cid, now],
    })),
  ]);
}

export async function removeSubscriber(userId: string, env: Env): Promise<boolean> {
  const db = getDb(env);
  const check = await db.execute({ sql: "SELECT 1 FROM subscribers WHERE user_id = ?", args: [userId] });
  if (check.rows.length === 0) return false;
  await db.execute({ sql: "DELETE FROM subscribers WHERE user_id = ?", args: [userId] });
  return true;
}

export async function getSubscriberChannels(userId: string, env: Env): Promise<string[]> {
  const db = getDb(env);
  const rs = await db.execute({ sql: "SELECT channel_id FROM subscribers WHERE user_id = ?", args: [userId] });
  return rs.rows.map((r) => String(r[0]));
}

async function sha256hex(text: string): Promise<string> {
  const data = new TextEncoder().encode(text);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(hashBuffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
