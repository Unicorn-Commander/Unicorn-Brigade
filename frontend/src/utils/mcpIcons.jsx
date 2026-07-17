import {
  Github, Drama, MessageSquare, Database, FolderOpen, Brain, Globe, Search,
  HardDrive, MousePointerClick, CreditCard, BarChart3, GitBranch, FileText,
  Table, Triangle, Cloud, Zap, Phone, Mail, Bug, Calendar, ShoppingBag,
  Ticket, ClipboardList, Target, Send, TrendingUp, Flame, Clapperboard, Server,
} from 'lucide-react';

/**
 * MCP server id → a lucide mark. Replaces the decorative emoji map that used to
 * live (duplicated) in MCPServerCard and MCPToolList, so category glyphs are
 * crisp vector icons that inherit currentColor instead of OS emoji.
 */
const ICONS = {
  github: Github,
  playwright: Drama,
  slack: MessageSquare,
  postgresql: Database,
  filesystem: FolderOpen,
  memory: Brain,
  fetch: Globe,
  brave_search: Search,
  google_drive: HardDrive,
  puppeteer: MousePointerClick,
  stripe: CreditCard,
  linear: BarChart3,
  git: GitBranch,
  notion: FileText,
  airtable: Table,
  vercel: Triangle,
  cloudflare: Cloud,
  supabase: Zap,
  twilio: Phone,
  sendgrid: Mail,
  sentry: Bug,
  monday: Calendar,
  shopify: ShoppingBag,
  salesforce: Cloud,
  zendesk: Ticket,
  jira: ClipboardList,
  hubspot: Target,
  mailchimp: Send,
  semrush: TrendingUp,
  zapier: Zap,
  amplitude: BarChart3,
  mixpanel: TrendingUp,
  hotjar: Flame,
  fullstory: Clapperboard,
};

export function getMcpServerIcon(name) {
  return ICONS[name] || Server;
}

/** Decorative server glyph (aria-hidden — the server name is always adjacent). */
export default function McpServerIcon({ name, className = 'w-6 h-6' }) {
  const Icon = getMcpServerIcon(name);
  return <Icon className={className} aria-hidden="true" />;
}
