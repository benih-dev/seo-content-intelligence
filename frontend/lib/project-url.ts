export function normalizeWebsiteUrl(input: string): string {
  const domain = input.trim();
  const websiteUrl = domain.includes("://") ? domain : `https://${domain}`;
  const website = URL.canParse(websiteUrl) ? new URL(websiteUrl) : null;
  if (!website || !["https:", "http:"].includes(website.protocol) || website.username || website.password || /\s/.test(domain)) {
    throw new Error("Enter a website domain such as example.com or https://example.com.");
  }
  return website.origin + website.pathname.replace(/\/+$/, "");
}
