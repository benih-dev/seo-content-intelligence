export const publicSettingFields = ["llm_model", "llm_api_base", "serp_provider", "dataforseo_login", "github_api_url"] as const;
export const secretSettingFields = ["llm_api_key", "dataforseo_password", "github_token"] as const;
export type PublicSetting = typeof publicSettingFields[number];
export type SecretSetting = typeof secretSettingFields[number];
export type SecretStatus = { configured: boolean; source: "db" | "env" | "none" };
export type AppSettings = Record<PublicSetting, string> & Record<SecretSetting, SecretStatus> & {
  modes: { llm: "mock" | "live"; serp: "mock" | "dataforseo" };
};

export function settingsPatch(initial: AppSettings, values: Record<PublicSetting, string>, secrets: Partial<Record<SecretSetting, string | null>>) {
  const patch: Record<string, string | null> = {};
  for (const key of publicSettingFields) {
    if (values[key] !== initial[key]) patch[key] = values[key];
  }
  for (const key of secretSettingFields) {
    if (secrets[key] === null || (typeof secrets[key] === "string" && secrets[key] !== "")) patch[key] = secrets[key];
  }
  return patch;
}

export function secretStatus(status: SecretStatus) {
  if (!status.configured) return "Not set";
  return status.source === "db" ? "Configured (saved in app)" : "Configured (from environment)";
}
