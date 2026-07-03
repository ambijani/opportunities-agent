/** Port of discord_bot/embed_builder.py — returns a Discord embed dict. */

import { isEmail } from "./discord";

/** Some startups list a contact email instead of an apply link. */
function applyUrl(url: string): string {
  return isEmail(url) ? `mailto:${url.replace(/^mailto:/i, "")}` : url;
}

const CATEGORY_DISPLAY: Record<string, string> = {
  "cs-engineering-tech":            "CS / Engineering / Tech",
  "business-finance-banking":       "Business / Finance / Banking",
  "consulting":                     "Consulting",
  "humanities-healthcare-medicine": "Humanities / Healthcare / Medicine",
  "programs":                       "Fellowships & Programs",
  "scholarships":                   "Scholarships",
};

const TYPE_LABEL: Record<string, string> = {
  internship: "[Internship]",
  full_time:  "[Full-Time]",
};

const SOURCE_DISPLAY: Record<string, string> = {
  github_readme: "GitHub (underclassmen-opportunities)",
  intern_list:   "intern-list.com",
  newgrad_jobs:  "newgrad-jobs.com",
  slack:         "Slack",
  manual:        "Manual submission",
};

const CATEGORY_COLORS: Record<string, number> = {
  "cs-engineering-tech":            0x5865f2,
  "business-finance-banking":       0xf0b429,
  "consulting":                     0x2d9b27,
  "humanities-healthcare-medicine": 0xed4245,
  "programs":                       0x9b59b6,
  "scholarships":                   0xe67e22,
};

export interface JobEmbed {
  title: string;
  company: string;
  location: string;
  datePosted: string;
  description?: string;
  url: string;
  jobType: string;
  category: string;
  source: string;
}

export function buildEmbed(job: JobEmbed): Record<string, unknown> {
  const isManual = job.source === "manual";
  const color = isManual ? 0xf39c12 : (CATEGORY_COLORS[job.category] ?? 0x9b59b6);
  const typeLabel = TYPE_LABEL[job.jobType] ?? "";
  const catLabel  = CATEGORY_DISPLAY[job.category] ?? "Programs & Fellowships";
  const srcLabel  = SOURCE_DISPLAY[job.source] ?? job.source;

  const title = `${isManual ? "📌 " : ""}${typeLabel}  ${job.title} — ${job.company}`;

  const fields: unknown[] = [
    { name: "Company",     value: (job.company   || "Unknown").slice(0, 1024), inline: true },
    { name: "Location",    value: (job.location  || "Unknown").slice(0, 1024), inline: true },
    { name: "Date Posted", value: (job.datePosted || "Unknown").slice(0, 1024), inline: true },
  ];
  if (job.description) {
    fields.push({ name: "Description", value: job.description.slice(0, 1024), inline: false });
  }
  const link = applyUrl(job.url);
  fields.push({
    name: "Apply",
    value: isEmail(job.url) ? `Email ${job.url} to apply` : `[Click here to apply](${link})`,
    inline: false,
  });

  const embed: Record<string, unknown> = {
    title: title.slice(0, 256),
    // Discord only hyperlinks the title for http(s) urls — omit it for mailto links.
    ...(isEmail(job.url) ? {} : { url: link }),
    color,
    timestamp: new Date().toISOString(),
    fields,
    footer:    { text: `Source: ${srcLabel}  •  ${catLabel}` },
  };
  if (isManual) {
    embed["author"] = { name: "✋ Manually Submitted Opportunity" };
  }
  return embed;
}
