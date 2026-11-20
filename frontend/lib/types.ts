export interface ProjectInput {
  name: string;
  domain: string;
  niche: string;
  audience: string;
  language: string;
  country: string;
  voice_profile: string;
  rules: Record<string, unknown>;
  business_objective: string;
}
export interface Project extends ProjectInput {
  id: string;
  version: number;
  created_at: string;
}
export interface ContentItem {
  id: string;
  url: string;
  title: string;
  slug: string;
  status: string;
  last_seen_at: string;
  metadata_json: { sitemap_lastmod?: string };
}
export interface Version {
  id: string;
  version: number;
  created_at: string;
}
export interface Intent {
  label: string;
  reason: string;
  confidence: number;
}
export interface ScoreDimension {
  score: number | null;
  weight: number;
  reason: string;
  confidence: number;
}
export interface Keyword extends Version {
  keyword: string;
  intent: string;
  selected: boolean;
  score: number;
  confidence: number;
  data: {
    intent: Intent;
    final_intent?: string;
    overlap_warnings?: { url: string; reason: string; recommendation: string }[];
    inventory_count?: number;
    inventory_missing_metadata?: number;
    metrics: {
      volume: number | null;
      competition: string | number | null;
      provider: string;
      status: string;
      locale: string;
      period: string;
      captured_at: string;
    };
    opportunity: {
      score: number;
      confidence: number;
      dimensions: Record<string, ScoreDimension>;
    };
    serp_snapshot_id: string;
  };
}
export interface BriefLink {
  url: string;
  title: string;
  anchor: string;
  reason: string;
  status: "inventory" | "search_suggestion";
}
export interface BriefData {
  angle: string;
  rationale: string;
  differentiation: string;
  audience: string;
  intent: string;
  outline: { level: number; heading: string; purpose: string }[];
  questions: string[];
  subtopics: string[];
  entities: string[];
  examples: string[];
  exclusions: string[];
  internal_links: BriefLink[];
  source_plan: string[];
}
export interface Brief extends Version {
  status: string;
  data: BriefData;
}
export interface SEO {
  title: string;
  h1: string;
  slug: string;
  meta_description: string;
  excerpt: string;
  tags: string[];
  category: string;
  primary_keyword: string;
  locale: string;
  image_guidance: { concept: string; alt: string; caption: string };
}
export interface Draft extends Version {
  body_md: string;
  body_html: string;
  metadata_json: SEO;
  status: string;
  data: { change_log: string };
}
export interface Finding {
  dimension: string;
  severity: string;
  location: string;
  finding: string;
  action: string;
}
export interface QAReview extends Version {
  draft_id: string;
  data: {
    dimensions: string[];
    findings: Finding[];
    status: string;
    summary: string;
    expert_review_required: boolean;
    human_resolution?: { comment: string; expert_reviewed: boolean };
  };
}
export interface Source extends Version {
  url: string;
  title: string;
  publisher: string;
  published_at: string | null;
  retrieved_at: string;
  data: { mock?: boolean; snippet: string };
}
export interface Evidence extends Version {
  source_id: string;
  claim: string;
  supporting_note: string;
  confidence: number;
  review_status: string;
  data: { url: string; scope: string };
}
export interface Audit extends Version {
  actor: string;
  action: string;
  data: Record<string, unknown>;
}
export interface Job {
  id: string;
  status: string;
  attempts: number;
  error: string | null;
}
export interface RunSummary {
  id: string;
  project_id: string;
  mode: string;
  primary_keyword: string;
  locale: string;
  state: string;
  created_at: string;
  updated_at: string;
  revision_count: number;
  error: string | null;
}
export interface Run extends RunSummary {
  revision_limit: number;
  mock_revision: boolean;
  context: { project?: Project };
  artifacts: (Version & { stage: string; data: Record<string, unknown> })[];
  keywords: Keyword[];
  briefs: Brief[];
  drafts: Draft[];
  qa_reviews: QAReview[];
  sources: Source[];
  evidence: Evidence[];
  audit: Audit[];
  jobs: Job[];
  exports: string[];
  serp_snapshots: (Version & {
    query: string;
    provider: string;
    locale: string;
    data: {
      captured_at: string;
      device: string;
      mock?: boolean;
      results: { rank: number; url: string; title: string; snippet: string }[];
    };
  })[];
  usage: {
    cost_usd: number;
    tokens: number;
    calls: {
      task: string;
      model: string;
      prompt_tokens: number;
      completion_tokens: number;
      cost_usd: number;
      latency_ms: number;
    }[];
  };
}
