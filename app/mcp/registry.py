"""
MCP Server Registry

Central management for all MCP (Model Context Protocol) servers.
Supports both subprocess-based servers (npm packages) and HTTP-based servers.
"""

import os
import asyncio
import subprocess
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

# Import MCPClient for proper protocol handling
from app.protocols.mcp import (
    MCPClient,
    MCPServerConfig,
    MCPTransport as ProtocolMCPTransport
)

logger = logging.getLogger(__name__)


class MCPTransport(Enum):
    """MCP transport types (registry-level enum, maps to protocol enum)"""
    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


@dataclass
class MCPServer:
    """MCP Server configuration"""
    name: str
    display_name: str
    command: str
    args: List[str]
    env: Dict[str, str] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    transport: MCPTransport = MCPTransport.STDIO
    port: Optional[int] = None
    description: str = ""
    enabled: bool = True

    def get_env(self) -> Dict[str, str]:
        """Get environment variables with substitutions"""
        result = {**os.environ}
        for key, value in self.env.items():
            if value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                result[key] = os.getenv(env_var, "")
            else:
                result[key] = value
        return result


class MCPRegistry:
    """
    Central registry for MCP servers.
    Manages lifecycle of MCP server processes.
    """

    # Built-in MCP server definitions
    SERVERS: Dict[str, MCPServer] = {
        "github": MCPServer(
            name="github",
            display_name="GitHub",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-github"],
            env={"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
            capabilities=[
                "create_repository", "create_branch", "create_or_update_file",
                "create_issue", "get_issue", "list_issues", "add_issue_comment",
                "create_pull_request", "get_pull_request", "list_pull_requests",
                "merge_pull_request", "search_code", "search_issues",
                "search_repositories", "get_file_contents", "list_commits"
            ],
            description="GitHub repository management - commits, PRs, issues, code search"
        ),

        "filesystem": MCPServer(
            name="filesystem",
            display_name="Filesystem",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem", "${WORKSPACE_PATH:-/workspace}"],
            capabilities=["read_file", "write_file", "list_directory", "search_files", "move_file", "get_file_info"],
            description="Local filesystem operations - read, write, search files"
        ),

        "postgres": MCPServer(
            name="postgres",
            display_name="PostgreSQL",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-postgres"],
            env={"DATABASE_URL": "${DATABASE_URL}"},
            capabilities=["query", "list_tables", "describe_table", "list_schemas"],
            description="PostgreSQL database - schema inspection and queries"
        ),

        "playwright": MCPServer(
            name="playwright",
            display_name="Playwright Browser",
            command="npx",
            args=["-y", "@playwright/mcp@latest", "--headless"],
            capabilities=[
                "browser_navigate", "browser_click", "browser_type", "browser_fill",
                "browser_snapshot", "browser_take_screenshot", "browser_select_option",
                "browser_hover", "browser_press_key", "browser_wait_for",
                "browser_evaluate", "browser_close"
            ],
            description="Browser automation via accessibility tree - fast, reliable"
        ),

        "slack": MCPServer(
            name="slack",
            display_name="Slack",
            command="npx",
            args=["-y", "@anthropic/mcp-server-slack"],
            env={
                "SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}",
                "SLACK_USER_TOKEN": "${SLACK_USER_TOKEN}",
            },
            capabilities=[
                "conversations_history", "conversations_replies", "conversations_search_messages",
                "conversations_add_message", "channels_list", "reactions_add"
            ],
            description="Slack workspace - channels, messages, search, DMs"
        ),

        "memory": MCPServer(
            name="memory",
            display_name="Memory",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-memory"],
            capabilities=["store", "retrieve", "list", "delete"],
            description="Persistent key-value memory storage"
        ),

        "fetch": MCPServer(
            name="fetch",
            display_name="HTTP Fetch",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-fetch"],
            capabilities=["fetch"],
            description="HTTP requests - GET, POST, PUT, DELETE"
        ),

        "brave-search": MCPServer(
            name="brave-search",
            display_name="Brave Search",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-brave-search"],
            env={"BRAVE_API_KEY": "${BRAVE_API_KEY}"},
            capabilities=["brave_web_search", "brave_local_search"],
            description="Brave Search API for web searches"
        ),

        "google-drive": MCPServer(
            name="google-drive",
            display_name="Google Drive",
            command="npx",
            args=["-y", "@anthropic/mcp-server-google-drive"],
            env={"GOOGLE_APPLICATION_CREDENTIALS": "${GOOGLE_APPLICATION_CREDENTIALS}"},
            capabilities=["search_files", "get_file", "list_files", "download_file"],
            description="Google Drive - search, read, organize documents"
        ),

        "puppeteer": MCPServer(
            name="puppeteer",
            display_name="Puppeteer",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-puppeteer"],
            capabilities=["navigate", "screenshot", "click", "fill", "evaluate"],
            description="Puppeteer browser control (alternative to Playwright)"
        ),

        # Phase 1 MCP Servers - January 2026

        "stripe": MCPServer(
            name="stripe",
            display_name="Stripe Payments",
            command="npx",
            args=["-y", "@stripe/agent-toolkit", "mcp"],
            env={"STRIPE_API_KEY": "${STRIPE_API_KEY}"},
            capabilities=[
                "create_payment_intent", "capture_payment_intent", "cancel_payment_intent",
                "create_customer", "update_customer", "retrieve_customer", "list_customers",
                "create_subscription", "update_subscription", "cancel_subscription", "retrieve_subscription",
                "create_invoice", "send_invoice", "retrieve_invoice", "list_invoices",
                "create_product", "update_product", "list_products",
                "create_price", "update_price", "list_prices",
                "retrieve_balance", "list_balance_transactions",
                "create_refund", "retrieve_refund", "list_refunds",
                "search_customers", "search_subscriptions", "search_invoices"
            ],
            description="Stripe payment processing - payments, subscriptions, customers, invoices, refunds"
        ),

        "linear": MCPServer(
            name="linear",
            display_name="Linear Project Management",
            command="npx",
            args=["-y", "@linear/mcp-server-linear"],
            env={"LINEAR_API_KEY": "${LINEAR_API_KEY}"},
            capabilities=[
                "create_issue", "update_issue", "delete_issue", "get_issue", "search_issues",
                "add_comment", "update_comment", "delete_comment",
                "create_project", "update_project", "list_projects",
                "list_teams", "get_team",
                "list_users", "get_user",
                "create_label", "list_labels",
                "list_workflows", "list_workflow_states",
                "list_cycles", "get_cycle",
                "list_milestones", "create_milestone",
                "get_organization"
            ],
            description="Linear issue tracking - issues, projects, teams, workflows, sprints"
        ),

        "git": MCPServer(
            name="git",
            display_name="Git Repository",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-git"],
            capabilities=[
                "git_status", "git_diff", "git_log", "git_show",
                "git_add", "git_commit", "git_reset",
                "git_branch", "git_checkout", "git_merge",
                "git_remote", "git_fetch", "git_pull", "git_push",
                "git_tag", "git_blame", "git_grep",
                "read_repository", "search_repository", "file_history"
            ],
            description="Git repository operations - commits, branches, history, local repo management"
        ),

        "notion": MCPServer(
            name="notion",
            display_name="Notion Workspace",
            command="npx",
            args=["-y", "@notionhq/notion-mcp-server"],
            env={
                "NOTION_API_KEY": "${NOTION_API_KEY}",
                "NOTION_VERSION": "2022-06-28"
            },
            capabilities=[
                "create_page", "update_page", "retrieve_page", "archive_page",
                "create_database", "update_database", "query_database", "retrieve_database",
                "search", "list_users", "retrieve_user",
                "append_block_children", "retrieve_block_children",
                "create_comment", "retrieve_comments"
            ],
            description="Notion workspace - pages, databases, tasks, wiki, team collaboration"
        ),

        # Phase 2 MCP Servers - January 2026

        "airtable": MCPServer(
            name="airtable",
            display_name="Airtable Database",
            command="npx",
            args=["-y", "@airtable/mcp-server"],
            env={
                "AIRTABLE_API_KEY": "${AIRTABLE_API_KEY}",
                "AIRTABLE_BASE_ID": "${AIRTABLE_BASE_ID}"
            },
            capabilities=[
                "create_record", "update_record", "delete_record", "get_record",
                "list_records", "query_records", "batch_create", "batch_update",
                "list_tables", "get_table_schema", "describe_table",
                "get_base_schema", "list_bases", "search_records",
                "create_field", "update_field", "delete_field",
                "get_view", "list_views"
            ],
            description="Airtable database operations - flexible spreadsheet-database hybrid"
        ),

        "vercel": MCPServer(
            name="vercel",
            display_name="Vercel Deployment",
            command="npx",
            args=["-y", "@vercel/mcp-server"],
            env={
                "VERCEL_TOKEN": "${VERCEL_TOKEN}",
                "VERCEL_TEAM_ID": "${VERCEL_TEAM_ID}"
            },
            capabilities=[
                "deploy_project", "create_deployment", "get_deployment", "list_deployments",
                "delete_deployment", "cancel_deployment", "promote_deployment",
                "list_projects", "get_project", "create_project", "update_project", "delete_project",
                "list_env_vars", "create_env_var", "update_env_var", "delete_env_var",
                "list_domains", "add_domain", "remove_domain", "verify_domain",
                "get_deployment_logs", "get_build_logs", "get_function_logs",
                "list_teams", "get_team"
            ],
            description="Vercel deployment platform - frontend hosting, serverless functions, edge network"
        ),

        "cloudflare": MCPServer(
            name="cloudflare",
            display_name="Cloudflare Edge Platform",
            command="npx",
            args=["-y", "@cloudflare/mcp-server"],
            env={
                "CLOUDFLARE_API_TOKEN": "${CLOUDFLARE_API_TOKEN}",
                "CLOUDFLARE_ACCOUNT_ID": "${CLOUDFLARE_ACCOUNT_ID}"
            },
            capabilities=[
                "deploy_worker", "create_worker", "update_worker", "delete_worker",
                "list_workers", "get_worker", "get_worker_logs",
                "kv_get", "kv_put", "kv_delete", "kv_list", "kv_list_namespaces",
                "r2_upload", "r2_download", "r2_delete", "r2_list", "r2_create_bucket",
                "list_zones", "get_zone", "purge_cache",
                "create_dns_record", "update_dns_record", "delete_dns_record", "list_dns_records",
                "get_analytics", "get_firewall_events", "get_zone_analytics",
                "create_page_rule", "list_page_rules", "update_page_rule"
            ],
            description="Cloudflare edge platform - Workers, KV storage, R2, DNS, CDN"
        ),

        "supabase": MCPServer(
            name="supabase",
            display_name="Supabase Backend",
            command="npx",
            args=["-y", "@supabase/mcp-server"],
            env={
                "SUPABASE_URL": "${SUPABASE_URL}",
                "SUPABASE_ANON_KEY": "${SUPABASE_ANON_KEY}",
                "SUPABASE_SERVICE_ROLE_KEY": "${SUPABASE_SERVICE_ROLE_KEY}"
            },
            capabilities=[
                "query_database", "execute_sql", "list_tables", "describe_table",
                "auth_create_user", "auth_update_user", "auth_delete_user", "auth_get_user", "auth_list_users",
                "auth_send_magic_link", "auth_verify_otp", "auth_sign_out",
                "storage_upload", "storage_download", "storage_delete", "storage_list",
                "storage_create_bucket", "storage_delete_bucket", "storage_list_buckets",
                "realtime_subscribe", "realtime_unsubscribe", "realtime_broadcast",
                "edge_functions_invoke", "edge_functions_list", "edge_functions_deploy"
            ],
            description="Supabase backend platform - PostgreSQL, auth, storage, real-time, edge functions"
        ),

        # Phase 3 MCP Servers - January 2026

        "mongodb": MCPServer(
            name="mongodb",
            display_name="MongoDB Database",
            command="npx",
            args=["-y", "@mongodb/mcp-server"],
            env={
                "MONGODB_URI": "${MONGODB_URI}",
                "MONGODB_DATABASE": "${MONGODB_DATABASE}"
            },
            capabilities=[
                "create_document", "update_document", "delete_document", "find_document",
                "find_many_documents", "count_documents", "distinct_values",
                "create_index", "list_indexes", "drop_index",
                "create_collection", "drop_collection", "list_collections",
                "aggregate", "bulk_write",
                "start_transaction", "commit_transaction", "abort_transaction",
                "validate_schema", "update_schema",
                "list_databases", "get_stats"
            ],
            description="MongoDB NoSQL database - document operations, aggregation, indexing, transactions"
        ),

        "twilio": MCPServer(
            name="twilio",
            display_name="Twilio Communications",
            command="npx",
            args=["-y", "@twilio/mcp-server"],
            env={
                "TWILIO_ACCOUNT_SID": "${TWILIO_ACCOUNT_SID}",
                "TWILIO_AUTH_TOKEN": "${TWILIO_AUTH_TOKEN}",
                "TWILIO_PHONE_NUMBER": "${TWILIO_PHONE_NUMBER}"
            },
            capabilities=[
                "send_sms", "send_mms", "list_messages", "get_message",
                "make_call", "list_calls", "get_call", "update_call",
                "send_whatsapp", "list_whatsapp_messages",
                "create_verification", "check_verification",
                "lookup_phone_number", "carrier_lookup",
                "list_available_numbers", "purchase_number",
                "create_conference", "list_conferences", "update_conference",
                "record_call", "transcribe_recording",
                "send_email", "list_emails",
                "get_account_info", "list_usage"
            ],
            description="Twilio multi-channel communications - SMS, voice, WhatsApp, email, verification"
        ),

        "sentry": MCPServer(
            name="sentry",
            display_name="Sentry Monitoring",
            command="npx",
            args=["-y", "@sentry/mcp-server"],
            env={
                "SENTRY_DSN": "${SENTRY_DSN}",
                "SENTRY_ORG": "${SENTRY_ORG}",
                "SENTRY_PROJECT": "${SENTRY_PROJECT}"
            },
            capabilities=[
                "list_issues", "get_issue", "update_issue", "resolve_issue",
                "add_comment", "list_comments",
                "list_events", "get_event", "get_event_trace",
                "create_release", "update_release", "list_releases",
                "associate_commits", "deploy_release",
                "create_alert_rule", "update_alert_rule", "list_alert_rules",
                "get_project_stats", "get_performance_stats",
                "list_transactions", "get_transaction_details"
            ],
            description="Sentry error tracking - issues, events, releases, alerts, performance monitoring"
        ),

        "hubspot": MCPServer(
            name="hubspot",
            display_name="HubSpot CRM",
            command="npx",
            args=["-y", "@hubspot/mcp-server"],
            env={
                "HUBSPOT_API_KEY": "${HUBSPOT_API_KEY}",
                "HUBSPOT_PORTAL_ID": "${HUBSPOT_PORTAL_ID}"
            },
            capabilities=[
                "create_contact", "update_contact", "delete_contact", "get_contact", "search_contacts",
                "create_company", "update_company", "delete_company", "get_company", "search_companies",
                "create_deal", "update_deal", "delete_deal", "get_deal", "search_deals",
                "create_ticket", "update_ticket", "delete_ticket", "get_ticket",
                "send_email", "schedule_email", "track_email_opens",
                "create_task", "update_task", "list_tasks",
                "create_note", "associate_note",
                "create_workflow", "trigger_workflow", "list_workflows",
                "get_analytics", "get_funnel_stats", "get_attribution_report",
                "list_pipelines", "get_pipeline_stage"
            ],
            description="HubSpot CRM - contacts, companies, deals, emails, workflows, marketing automation"
        ),

        # Phase 4 MCP Servers - January 2026

        "shopify": MCPServer(
            name="shopify",
            display_name="Shopify E-Commerce",
            command="npx",
            args=["-y", "@shopify/mcp-server"],
            env={
                "SHOPIFY_SHOP_URL": "${SHOPIFY_SHOP_URL}",
                "SHOPIFY_ACCESS_TOKEN": "${SHOPIFY_ACCESS_TOKEN}",
                "SHOPIFY_API_VERSION": "${SHOPIFY_API_VERSION}"
            },
            capabilities=[
                "create_product", "update_product", "delete_product", "get_product", "list_products",
                "create_variant", "update_variant", "delete_variant", "list_variants",
                "create_collection", "update_collection", "delete_collection", "list_collections",
                "create_order", "update_order", "get_order", "list_orders", "cancel_order",
                "create_customer", "update_customer", "delete_customer", "get_customer", "search_customers",
                "get_inventory", "adjust_inventory", "list_inventory_levels",
                "create_fulfillment", "update_fulfillment", "cancel_fulfillment", "track_fulfillment",
                "create_discount", "update_discount", "delete_discount", "list_discounts",
                "get_analytics", "get_sales_report", "get_traffic_report"
            ],
            description="Shopify e-commerce platform - products, orders, customers, inventory, fulfillment"
        ),

        "salesforce": MCPServer(
            name="salesforce",
            display_name="Salesforce CRM",
            command="npx",
            args=["-y", "@salesforce/mcp-server"],
            env={
                "SALESFORCE_INSTANCE_URL": "${SALESFORCE_INSTANCE_URL}",
                "SALESFORCE_CLIENT_ID": "${SALESFORCE_CLIENT_ID}",
                "SALESFORCE_CLIENT_SECRET": "${SALESFORCE_CLIENT_SECRET}",
                "SALESFORCE_USERNAME": "${SALESFORCE_USERNAME}",
                "SALESFORCE_PASSWORD": "${SALESFORCE_PASSWORD}"
            },
            capabilities=[
                "create_lead", "update_lead", "delete_lead", "convert_lead", "get_lead", "search_leads",
                "create_contact", "update_contact", "delete_contact", "get_contact", "search_contacts",
                "create_account", "update_account", "delete_account", "get_account", "search_accounts",
                "create_opportunity", "update_opportunity", "delete_opportunity", "close_opportunity", "search_opportunities",
                "create_campaign", "update_campaign", "get_campaign", "list_campaigns", "add_campaign_members",
                "create_case", "update_case", "close_case", "get_case", "list_cases",
                "create_task", "update_task", "complete_task", "list_tasks",
                "run_report", "export_report", "list_reports",
                "create_dashboard", "update_dashboard", "list_dashboards",
                "execute_workflow", "list_workflows"
            ],
            description="Salesforce enterprise CRM - leads, contacts, accounts, opportunities, campaigns, cases"
        ),

        "jira": MCPServer(
            name="jira",
            display_name="Jira Project Management",
            command="npx",
            args=["-y", "@atlassian/jira-mcp-server"],
            env={
                "JIRA_HOST": "${JIRA_HOST}",
                "JIRA_EMAIL": "${JIRA_EMAIL}",
                "JIRA_API_TOKEN": "${JIRA_API_TOKEN}"
            },
            capabilities=[
                "create_issue", "update_issue", "delete_issue", "get_issue", "search_issues", "assign_issue",
                "add_comment", "update_comment", "delete_comment", "list_comments",
                "transition_issue", "list_transitions", "get_workflow",
                "create_sprint", "start_sprint", "close_sprint", "list_sprints", "add_to_sprint",
                "create_board", "get_board", "list_boards",
                "create_project", "update_project", "get_project", "list_projects",
                "add_attachment", "download_attachment", "list_attachments",
                "create_filter", "update_filter", "list_filters", "share_filter",
                "link_issues", "get_issue_links"
            ],
            description="Jira project management - issues, sprints, boards, workflows, projects, agile tracking"
        ),

        "zendesk": MCPServer(
            name="zendesk",
            display_name="Zendesk Support",
            command="npx",
            args=["-y", "@zendesk/mcp-server"],
            env={
                "ZENDESK_SUBDOMAIN": "${ZENDESK_SUBDOMAIN}",
                "ZENDESK_EMAIL": "${ZENDESK_EMAIL}",
                "ZENDESK_API_TOKEN": "${ZENDESK_API_TOKEN}"
            },
            capabilities=[
                "create_ticket", "update_ticket", "delete_ticket", "get_ticket", "search_tickets", "merge_tickets",
                "add_comment", "list_comments",
                "create_user", "update_user", "suspend_user", "get_user", "search_users",
                "create_organization", "update_organization", "get_organization", "list_organizations",
                "create_group", "update_group", "list_groups", "assign_to_group",
                "create_macro", "update_macro", "list_macros", "apply_macro",
                "create_trigger", "update_trigger", "list_triggers",
                "create_automation", "update_automation", "list_automations",
                "create_view", "list_views", "execute_view",
                "search_help_center", "create_article", "update_article"
            ],
            description="Zendesk customer support - tickets, users, organizations, macros, triggers, help center"
        ),

        # Phase 5 MCP Servers - January 2026

        "intercom": MCPServer(
            name="intercom",
            display_name="Intercom Messaging",
            command="npx",
            args=["-y", "@intercom/mcp-server"],
            env={
                "INTERCOM_ACCESS_TOKEN": "${INTERCOM_ACCESS_TOKEN}",
                "INTERCOM_APP_ID": "${INTERCOM_APP_ID}"
            },
            capabilities=[
                "create_conversation", "get_conversation", "list_conversations", "reply_to_conversation", "close_conversation",
                "assign_conversation", "snooze_conversation", "tag_conversation",
                "create_contact", "update_contact", "delete_contact", "get_contact", "search_contacts", "merge_contacts",
                "add_tag", "remove_tag", "list_tags",
                "create_note", "list_notes",
                "create_ticket", "update_ticket", "get_ticket", "list_tickets",
                "send_message", "send_email",
                "list_teams", "list_admins",
                "create_article", "update_article", "get_article", "search_articles",
                "get_company", "create_company", "update_company", "list_companies"
            ],
            description="Intercom customer messaging - conversations, contacts, live chat, support tickets, help center"
        ),

        "asana": MCPServer(
            name="asana",
            display_name="Asana Work Management",
            command="npx",
            args=["-y", "@asana/mcp-server"],
            env={
                "ASANA_ACCESS_TOKEN": "${ASANA_ACCESS_TOKEN}",
                "ASANA_WORKSPACE_GID": "${ASANA_WORKSPACE_GID}"
            },
            capabilities=[
                "create_task", "update_task", "delete_task", "get_task", "search_tasks", "duplicate_task",
                "add_comment", "list_comments",
                "create_project", "update_project", "delete_project", "get_project", "list_projects", "duplicate_project",
                "create_section", "update_section", "delete_section", "list_sections",
                "add_task_to_project", "remove_task_from_project", "move_task",
                "create_portfolio", "update_portfolio", "list_portfolios",
                "create_goal", "update_goal", "list_goals",
                "list_teams", "get_team",
                "list_workspaces", "get_workspace",
                "list_users", "get_user",
                "add_tag", "remove_tag", "list_tags"
            ],
            description="Asana work management - tasks, projects, teams, portfolios, goals, collaboration"
        ),

        "trello": MCPServer(
            name="trello",
            display_name="Trello Boards",
            command="npx",
            args=["-y", "@trello/mcp-server"],
            env={
                "TRELLO_API_KEY": "${TRELLO_API_KEY}",
                "TRELLO_API_TOKEN": "${TRELLO_API_TOKEN}"
            },
            capabilities=[
                "create_board", "update_board", "delete_board", "get_board", "list_boards",
                "create_list", "update_list", "archive_list", "get_list", "list_lists",
                "create_card", "update_card", "delete_card", "get_card", "list_cards", "move_card",
                "add_comment", "update_comment", "delete_comment", "list_comments",
                "add_member", "remove_member", "list_members",
                "create_label", "update_label", "delete_label", "list_labels", "add_label_to_card",
                "create_checklist", "update_checklist", "delete_checklist", "list_checklists",
                "add_attachment", "delete_attachment", "list_attachments"
            ],
            description="Trello visual project management - boards, lists, cards, checklists, labels, kanban workflows"
        ),

        "quickbooks": MCPServer(
            name="quickbooks",
            display_name="QuickBooks Accounting",
            command="npx",
            args=["-y", "@quickbooks/mcp-server"],
            env={
                "QUICKBOOKS_CLIENT_ID": "${QUICKBOOKS_CLIENT_ID}",
                "QUICKBOOKS_CLIENT_SECRET": "${QUICKBOOKS_CLIENT_SECRET}",
                "QUICKBOOKS_REALM_ID": "${QUICKBOOKS_REALM_ID}",
                "QUICKBOOKS_REFRESH_TOKEN": "${QUICKBOOKS_REFRESH_TOKEN}"
            },
            capabilities=[
                "create_invoice", "update_invoice", "delete_invoice", "get_invoice", "list_invoices", "send_invoice",
                "create_payment", "update_payment", "get_payment", "list_payments",
                "create_customer", "update_customer", "delete_customer", "get_customer", "list_customers", "search_customers",
                "create_vendor", "update_vendor", "delete_vendor", "get_vendor", "list_vendors",
                "create_bill", "update_bill", "delete_bill", "get_bill", "list_bills",
                "create_estimate", "update_estimate", "get_estimate", "list_estimates", "send_estimate",
                "create_expense", "update_expense", "get_expense", "list_expenses",
                "create_purchase_order", "update_purchase_order", "get_purchase_order",
                "get_profit_loss_report", "get_balance_sheet_report", "get_cash_flow_report",
                "list_accounts", "get_account", "create_account"
            ],
            description="QuickBooks accounting platform - invoices, payments, customers, vendors, expenses, financial reports"
        ),

        # Phase 6 MCP Servers - January 2026

        "mailchimp": MCPServer(
            name="mailchimp",
            display_name="Mailchimp Marketing",
            command="npx",
            args=["-y", "@mailchimp/mcp-server"],
            env={
                "MAILCHIMP_API_KEY": "${MAILCHIMP_API_KEY}",
                "MAILCHIMP_SERVER_PREFIX": "${MAILCHIMP_SERVER_PREFIX}"
            },
            capabilities=[
                "create_campaign", "update_campaign", "delete_campaign", "get_campaign", "list_campaigns", "send_campaign",
                "schedule_campaign", "pause_campaign", "resume_campaign", "replicate_campaign",
                "create_list", "update_list", "delete_list", "get_list", "list_lists",
                "add_member", "update_member", "delete_member", "get_member", "list_members", "batch_subscribe",
                "create_segment", "update_segment", "delete_segment", "list_segments",
                "create_tag", "apply_tag", "remove_tag", "list_tags",
                "create_template", "update_template", "delete_template", "get_template", "list_templates",
                "get_campaign_report", "get_campaign_stats", "get_list_growth", "get_engagement_stats"
            ],
            description="Mailchimp email marketing - campaigns, newsletters, audience management, automation, analytics"
        ),

        "activecampaign": MCPServer(
            name="activecampaign",
            display_name="ActiveCampaign Marketing",
            command="npx",
            args=["-y", "@activecampaign/mcp-server"],
            env={
                "ACTIVECAMPAIGN_URL": "${ACTIVECAMPAIGN_URL}",
                "ACTIVECAMPAIGN_API_KEY": "${ACTIVECAMPAIGN_API_KEY}"
            },
            capabilities=[
                "create_contact", "update_contact", "delete_contact", "get_contact", "list_contacts", "search_contacts",
                "create_deal", "update_deal", "delete_deal", "get_deal", "list_deals", "move_deal",
                "create_account", "update_account", "delete_account", "get_account", "list_accounts",
                "create_automation", "update_automation", "get_automation", "list_automations",
                "trigger_automation", "subscribe_to_automation", "unsubscribe_from_automation",
                "create_campaign", "send_campaign", "get_campaign", "list_campaigns",
                "create_list", "update_list", "delete_list", "get_list", "list_lists",
                "subscribe_contact", "unsubscribe_contact", "update_list_status",
                "create_tag", "apply_tag", "remove_tag", "list_tags",
                "create_task", "update_task", "complete_task", "list_tasks",
                "get_contact_score", "update_contact_score", "list_contact_activities",
                "create_pipeline", "update_pipeline", "list_pipelines", "get_pipeline_stage"
            ],
            description="ActiveCampaign marketing automation - advanced email, CRM, lead scoring, sales automation, pipelines"
        ),

        "calendly": MCPServer(
            name="calendly",
            display_name="Calendly Scheduling",
            command="npx",
            args=["-y", "@calendly/mcp-server"],
            env={
                "CALENDLY_API_KEY": "${CALENDLY_API_KEY}",
                "CALENDLY_WEBHOOK_SIGNING_KEY": "${CALENDLY_WEBHOOK_SIGNING_KEY}"
            },
            capabilities=[
                "get_user", "list_users", "get_organization",
                "create_event_type", "update_event_type", "delete_event_type", "get_event_type", "list_event_types",
                "get_scheduled_event", "list_scheduled_events", "cancel_scheduled_event",
                "get_invitee", "list_invitees", "create_invitee_no_show",
                "create_webhook", "update_webhook", "delete_webhook", "get_webhook", "list_webhooks",
                "create_routing_form", "update_routing_form", "get_routing_form", "list_routing_forms",
                "get_availability", "list_user_availability_schedules",
                "create_one_off_event_type", "get_organization_membership", "list_organization_memberships",
                "get_data_compliance", "delete_invitee_data"
            ],
            description="Calendly meeting scheduling - automated booking, calendar sync, team scheduling, workflow integration"
        ),

        "docusign": MCPServer(
            name="docusign",
            display_name="DocuSign eSignature",
            command="npx",
            args=["-y", "@docusign/mcp-server"],
            env={
                "DOCUSIGN_INTEGRATION_KEY": "${DOCUSIGN_INTEGRATION_KEY}",
                "DOCUSIGN_USER_ID": "${DOCUSIGN_USER_ID}",
                "DOCUSIGN_ACCOUNT_ID": "${DOCUSIGN_ACCOUNT_ID}",
                "DOCUSIGN_PRIVATE_KEY": "${DOCUSIGN_PRIVATE_KEY}"
            },
            capabilities=[
                "create_envelope", "send_envelope", "get_envelope", "list_envelopes", "delete_envelope",
                "void_envelope", "update_envelope", "get_envelope_status", "resend_envelope",
                "create_recipient", "update_recipient", "get_recipient", "list_recipients",
                "add_document", "get_document", "list_documents", "delete_document",
                "create_template", "update_template", "get_template", "list_templates", "delete_template",
                "apply_template_to_envelope", "create_envelope_from_template",
                "add_signer", "add_carbon_copy", "set_signing_order",
                "create_tab", "update_tab", "get_tabs", "add_signature_field", "add_text_field",
                "get_form_data", "download_envelope", "get_certificate",
                "create_brand", "update_brand", "list_brands",
                "get_audit_events", "download_audit_trail"
            ],
            description="DocuSign electronic signatures - contract automation, e-signatures, document workflow, compliance"
        ),

        # Phase 7 MCP Servers - January 2026

        "ahrefs": MCPServer(
            name="ahrefs",
            display_name="Ahrefs SEO Platform",
            command="npx",
            args=["-y", "@ahrefs/mcp-server"],
            env={
                "AHREFS_API_KEY": "${AHREFS_API_KEY}"
            },
            capabilities=[
                "get_domain_rating", "get_backlinks", "get_referring_domains", "analyze_backlink_profile",
                "check_broken_backlinks", "get_new_backlinks", "get_lost_backlinks",
                "keyword_research", "get_keyword_difficulty", "get_search_volume", "get_keyword_ideas",
                "analyze_serp", "get_organic_keywords", "get_top_pages", "get_content_gap",
                "site_audit", "get_health_score", "list_crawl_issues", "analyze_internal_links",
                "get_anchor_text_distribution", "check_toxic_backlinks",
                "rank_tracker", "get_ranking_history", "track_competitor_rankings",
                "get_traffic_estimate", "analyze_competitor_traffic", "get_traffic_sources",
                "content_explorer", "search_content", "get_top_content", "analyze_trending_topics",
                "link_intersect", "find_link_opportunities"
            ],
            description="Ahrefs SEO and backlink analysis - keyword research, competitor analysis, backlink monitoring, site audits"
        ),

        "semrush": MCPServer(
            name="semrush",
            display_name="SEMrush Marketing Toolkit",
            command="npx",
            args=["-y", "@semrush/mcp-server"],
            env={
                "SEMRUSH_API_KEY": "${SEMRUSH_API_KEY}"
            },
            capabilities=[
                "domain_overview", "get_organic_search_positions", "get_backlinks_overview", "get_domain_rank",
                "keyword_overview", "get_keyword_difficulty", "get_search_volume", "get_cpc_data",
                "keyword_magic_tool", "get_related_keywords", "get_question_keywords", "get_keyword_variations",
                "competitor_analysis", "get_organic_competitors", "get_paid_competitors", "compare_domains",
                "backlink_analytics", "get_referring_domains", "analyze_backlink_types", "get_anchor_text",
                "check_toxic_score", "get_backlink_gap",
                "site_audit", "get_site_health", "list_site_errors", "get_crawlability_issues",
                "analyze_core_web_vitals", "check_https_implementation",
                "position_tracking", "track_keyword_rankings", "get_ranking_distribution", "monitor_serp_features",
                "organic_research", "get_top_organic_keywords", "get_top_pages", "analyze_traffic_analytics",
                "advertising_research", "get_ad_copies", "get_ppc_keywords", "analyze_ad_history",
                "content_marketing", "get_topic_research", "analyze_seo_content_template", "get_content_ideas"
            ],
            description="SEMrush all-in-one marketing toolkit - SEO audits, keyword research, competitor tracking, PPC analytics"
        ),

        "zapier": MCPServer(
            name="zapier",
            display_name="Zapier Automation Platform",
            command="npx",
            args=["-y", "@zapier/mcp-server"],
            env={
                "ZAPIER_API_KEY": "${ZAPIER_API_KEY}"
            },
            capabilities=[
                "create_zap", "update_zap", "delete_zap", "get_zap", "list_zaps",
                "turn_on_zap", "turn_off_zap", "get_zap_history", "get_zap_runs",
                "create_trigger", "update_trigger", "list_available_triggers", "test_trigger",
                "create_action", "update_action", "list_available_actions", "test_action",
                "create_filter", "update_filter", "create_formatter", "create_delay",
                "create_path", "add_path_rule", "create_loop",
                "search_apps", "get_app_info", "list_app_triggers", "list_app_actions",
                "authenticate_app", "test_app_authentication", "refresh_app_connection",
                "create_webhook", "update_webhook", "delete_webhook", "catch_webhook",
                "store_data", "retrieve_data", "update_storage",
                "get_zap_analytics", "get_task_usage", "get_execution_logs",
                "create_folder", "move_zap_to_folder", "share_zap", "transfer_zap",
                "create_schedule", "update_schedule_frequency",
                "batch_create_zaps", "duplicate_zap", "export_zap", "import_zap"
            ],
            description="Zapier workflow automation - connect 6,000+ apps, multi-step automation, trigger-action workflows, data transformation"
        ),

        "make": MCPServer(
            name="make",
            display_name="Make Automation Platform",
            command="npx",
            args=["-y", "@make/mcp-server"],
            env={
                "MAKE_API_KEY": "${MAKE_API_KEY}",
                "MAKE_TEAM_ID": "${MAKE_TEAM_ID}"
            },
            capabilities=[
                "create_scenario", "update_scenario", "delete_scenario", "get_scenario", "list_scenarios",
                "activate_scenario", "deactivate_scenario", "run_scenario_once", "clone_scenario",
                "get_scenario_blueprint", "import_scenario_blueprint", "export_scenario_blueprint",
                "create_module", "update_module", "delete_module", "list_available_modules",
                "configure_trigger", "configure_action", "test_module",
                "create_router", "add_route", "set_route_filter", "create_aggregator",
                "create_iterator", "create_repeater",
                "add_error_handler", "configure_fallback_route", "set_commit_behavior",
                "create_data_store", "get_data_store", "add_data_record", "search_data_store",
                "create_webhook", "update_webhook", "delete_webhook", "get_webhook_url",
                "create_connection", "update_connection", "test_connection", "list_connections",
                "get_execution_history", "get_execution_details", "get_incomplete_executions",
                "resolve_execution", "rollback_execution",
                "create_organization", "list_teams", "get_team", "invite_team_member",
                "get_operations_usage", "get_scenario_statistics",
                "create_function", "update_function", "list_custom_functions",
                "schedule_scenario", "update_schedule_interval"
            ],
            description="Make visual automation platform - advanced workflows, visual builder, data transformation, API integrations"
        ),

        # Phase 8 MCP Servers - January 2026

        "amplitude": MCPServer(
            name="amplitude",
            display_name="Amplitude Analytics",
            command="npx",
            args=["-y", "@amplitude/mcp-server"],
            env={
                "AMPLITUDE_API_KEY": "${AMPLITUDE_API_KEY}",
                "AMPLITUDE_SECRET_KEY": "${AMPLITUDE_SECRET_KEY}",
                "AMPLITUDE_PROJECT_ID": "${AMPLITUDE_PROJECT_ID}"
            },
            capabilities=[
                "track_event", "identify_user", "set_user_properties", "set_group",
                "get_user_activity", "get_event_segmentation", "get_event_list",
                "create_cohort", "get_cohort", "list_cohorts", "export_cohort",
                "get_retention_analysis", "get_funnel_analysis", "create_funnel", "list_funnels",
                "get_revenue_analysis", "get_user_composition", "get_ltv_analysis",
                "create_dashboard", "get_dashboard", "list_dashboards", "share_dashboard",
                "run_query", "get_active_users", "get_new_users", "get_user_sessions",
                "create_experiment", "get_experiment_results", "list_experiments",
                "get_path_analysis", "get_impact_analysis", "get_stickiness",
                "create_custom_event", "update_taxonomy", "validate_events",
                "get_chart_data", "export_data", "get_annotations",
                "create_team", "manage_team_members", "get_project_settings",
                "create_behavioral_cohort", "get_real_time_data", "get_historical_data"
            ],
            description="Amplitude product analytics - user behavior tracking, funnel analysis, retention cohorts, A/B testing, behavioral analytics"
        ),

        "mixpanel": MCPServer(
            name="mixpanel",
            display_name="Mixpanel Analytics",
            command="npx",
            args=["-y", "@mixpanel/mcp-server"],
            env={
                "MIXPANEL_PROJECT_TOKEN": "${MIXPANEL_PROJECT_TOKEN}",
                "MIXPANEL_API_SECRET": "${MIXPANEL_API_SECRET}",
                "MIXPANEL_SERVICE_ACCOUNT": "${MIXPANEL_SERVICE_ACCOUNT}"
            },
            capabilities=[
                "track_event", "track_batch_events", "identify_user", "set_profile",
                "increment_property", "append_to_list", "union_list",
                "get_insights_query", "get_segmentation", "get_funnel", "get_retention",
                "get_addiction", "get_formulas", "get_flows", "get_revenue",
                "create_cohort", "get_cohort", "list_cohorts", "update_cohort",
                "export_cohort", "export_people_profiles", "engage_query",
                "get_jql_query", "run_custom_query",
                "create_board", "get_board", "list_boards", "share_board",
                "create_bookmark", "get_bookmark", "list_bookmarks",
                "get_events", "get_top_events", "get_event_properties",
                "get_user_profile", "get_user_activity", "get_user_journey",
                "create_experiment", "get_experiment", "list_experiments", "analyze_experiment",
                "predict_user_behavior", "get_impact_report", "get_signal_analysis",
                "create_alert", "get_alert", "list_alerts", "trigger_alert",
                "export_raw_data", "import_data", "manage_lexicon",
                "get_project_settings", "manage_project_users", "get_data_pipeline"
            ],
            description="Mixpanel advanced product analytics - event tracking, user journey analysis, retention reports, predictive analytics, behavioral cohorts"
        ),

        "segment": MCPServer(
            name="segment",
            display_name="Segment CDP",
            command="npx",
            args=["-y", "@segment/mcp-server"],
            env={
                "SEGMENT_WRITE_KEY": "${SEGMENT_WRITE_KEY}",
                "SEGMENT_ACCESS_TOKEN": "${SEGMENT_ACCESS_TOKEN}",
                "SEGMENT_WORKSPACE_SLUG": "${SEGMENT_WORKSPACE_SLUG}"
            },
            capabilities=[
                "track_event", "identify_user", "group_users", "alias_user", "page_view", "screen_view",
                "batch_events", "validate_event",
                "get_sources", "create_source", "update_source", "delete_source",
                "get_destinations", "create_destination", "update_destination", "enable_destination",
                "get_tracking_plan", "create_tracking_plan", "update_tracking_plan", "validate_tracking_plan",
                "get_schema", "update_schema", "validate_schema",
                "get_warehouses", "create_warehouse", "configure_warehouse_sync",
                "get_functions", "create_function", "update_function", "deploy_function",
                "get_audiences", "create_audience", "update_audience", "compute_audience",
                "get_traits", "create_trait", "get_computed_traits",
                "get_user_profile", "merge_profiles", "delete_profile",
                "get_connections", "test_connection", "sync_connection",
                "get_transformations", "create_transformation", "enable_transformation",
                "get_reverse_etl", "configure_reverse_etl", "sync_reverse_etl",
                "get_privacy_settings", "configure_consent", "manage_suppressions",
                "get_workspace_settings", "manage_workspace_users", "get_workspace_events"
            ],
            description="Segment customer data platform - unified data collection, 300+ integrations, data warehouse sync, identity resolution, event tracking"
        ),

        "posthog": MCPServer(
            name="posthog",
            display_name="PostHog Analytics",
            command="npx",
            args=["-y", "@posthog/mcp-server"],
            env={
                "POSTHOG_API_KEY": "${POSTHOG_API_KEY}",
                "POSTHOG_HOST": "${POSTHOG_HOST}",
                "POSTHOG_PROJECT_ID": "${POSTHOG_PROJECT_ID}"
            },
            capabilities=[
                "capture_event", "identify_user", "set_person_properties", "alias_person",
                "get_insights", "create_insight", "update_insight", "delete_insight",
                "get_trends", "get_funnels", "get_retention", "get_paths", "get_lifecycle",
                "create_dashboard", "get_dashboard", "list_dashboards", "share_dashboard",
                "create_cohort", "get_cohort", "list_cohorts", "calculate_cohort",
                "get_events", "get_event_definitions", "get_property_definitions",
                "create_action", "get_action", "list_actions", "update_action",
                "get_session_recordings", "get_recording", "list_recordings", "delete_recording",
                "create_feature_flag", "get_feature_flag", "list_feature_flags", "update_feature_flag",
                "evaluate_feature_flag", "get_feature_flag_activity",
                "create_experiment", "get_experiment", "list_experiments", "launch_experiment",
                "get_experiment_results", "end_experiment",
                "get_heatmaps", "create_heatmap", "get_toolbar_actions",
                "get_annotations", "create_annotation", "delete_annotation",
                "get_persons", "get_person", "merge_persons", "delete_person",
                "export_events", "query_events", "get_query_results",
                "get_project_settings", "update_project_settings", "manage_team_members"
            ],
            description="PostHog open-source product analytics - self-hosted analytics, session replay, feature flags, A/B testing, heatmaps, funnels"
        ),

        # Phase 9 MCP Servers - January 2026
        # UX & Product Analytics Platforms

        "heap": MCPServer(
            name="heap",
            display_name="Heap Auto-Capture Analytics",
            command="npx",
            args=["-y", "@heap/mcp-server"],
            env={
                "HEAP_APP_ID": "${HEAP_APP_ID}",
                "HEAP_API_KEY": "${HEAP_API_KEY}",
                "HEAP_ACCOUNT_ID": "${HEAP_ACCOUNT_ID}"
            },
            capabilities=[
                "capture_event", "identify_user", "add_user_properties", "remove_user_properties",
                "get_autocaptured_events", "list_event_definitions", "get_event_properties",
                "create_segment", "update_segment", "delete_segment", "get_segment", "list_segments",
                "export_segment", "get_segment_users",
                "create_funnel", "get_funnel", "list_funnels", "analyze_funnel",
                "get_retention_analysis", "get_path_analysis", "get_session_replay",
                "list_sessions", "get_session_details", "filter_sessions_by_events",
                "get_user_journey", "get_user_sessions", "get_user_profile",
                "create_dashboard", "get_dashboard", "list_dashboards", "share_dashboard",
                "export_data", "query_events", "get_sql_query_results",
                "get_campaign_attribution", "get_revenue_analysis", "get_conversion_metrics",
                "create_alert", "get_alert", "list_alerts", "trigger_alert",
                "get_page_views", "analyze_form_submissions", "track_rage_clicks",
                "get_autocapture_status", "enable_autocapture", "disable_autocapture"
            ],
            description="Heap auto-capture analytics - retroactive analytics, event autocapture, session replay, user journey analysis"
        ),

        "pendo": MCPServer(
            name="pendo",
            display_name="Pendo Product Experience",
            command="npx",
            args=["-y", "@pendo/mcp-server"],
            env={
                "PENDO_API_KEY": "${PENDO_API_KEY}",
                "PENDO_SUBDOMAIN": "${PENDO_SUBDOMAIN}",
                "PENDO_INTEGRATION_KEY": "${PENDO_INTEGRATION_KEY}"
            },
            capabilities=[
                "track_event", "identify_visitor", "identify_account", "update_metadata",
                "create_guide", "update_guide", "publish_guide", "get_guide", "list_guides", "delete_guide",
                "activate_guide", "deactivate_guide", "get_guide_analytics", "get_guide_views",
                "create_feature", "update_feature", "get_feature", "list_features", "tag_feature",
                "get_feature_adoption", "get_feature_usage", "analyze_feature_retention",
                "create_segment", "update_segment", "get_segment", "list_segments", "export_segment",
                "create_page", "update_page", "get_page", "list_pages", "tag_page",
                "get_page_analytics", "get_page_views", "get_click_metrics",
                "create_poll", "update_poll", "launch_poll", "get_poll_results", "list_polls",
                "create_nps_survey", "launch_nps_survey", "get_nps_results", "get_nps_trends",
                "get_visitor_activity", "get_visitor_journey", "get_account_health",
                "get_adoption_report", "get_retention_report", "get_sentiment_report",
                "create_product_area", "get_product_area", "analyze_product_area_usage",
                "create_roadmap_item", "update_roadmap_status", "get_feedback_requests",
                "export_analytics_data", "get_events", "query_custom_events",
                "create_track_event", "list_track_events", "get_track_event_analytics"
            ],
            description="Pendo product experience platform - in-app guidance, feature adoption tracking, user sentiment, product roadmap feedback"
        ),

        "fullstory": MCPServer(
            name="fullstory",
            display_name="FullStory Digital Experience",
            command="npx",
            args=["-y", "@fullstory/mcp-server"],
            env={
                "FULLSTORY_API_KEY": "${FULLSTORY_API_KEY}",
                "FULLSTORY_ORG_ID": "${FULLSTORY_ORG_ID}"
            },
            capabilities=[
                "get_session_replay", "get_session", "list_sessions", "search_sessions",
                "get_user_sessions", "get_session_events", "get_session_url",
                "identify_user", "set_user_properties", "get_user_profile", "search_users",
                "create_event", "track_custom_event", "get_events", "list_event_definitions",
                "create_segment", "update_segment", "get_segment", "list_segments", "export_segment",
                "get_funnel", "create_funnel", "analyze_funnel", "get_funnel_drop_offs",
                "get_conversion_metrics", "get_rage_clicks", "get_error_clicks", "get_dead_clicks",
                "detect_frustrated_users", "get_frustration_signals", "analyze_user_struggle",
                "get_page_views", "get_page_analytics", "get_click_heatmap",
                "create_dashboard", "get_dashboard", "list_dashboards", "share_dashboard",
                "get_search_results", "create_saved_search", "list_saved_searches",
                "export_data", "get_data_export_status", "download_export",
                "get_metrics", "get_custom_metrics", "create_metric_alert",
                "get_revenue_analysis", "track_conversions", "get_journey_analysis",
                "get_console_errors", "get_network_errors", "get_javascript_errors",
                "create_watchlist", "add_to_watchlist", "get_watchlist_alerts"
            ],
            description="FullStory digital experience intelligence - session replay, rage clicks, conversion funnels, frustrated user detection"
        ),

        "hotjar": MCPServer(
            name="hotjar",
            display_name="Hotjar UX Optimization",
            command="npx",
            args=["-y", "@hotjar/mcp-server"],
            env={
                "HOTJAR_API_KEY": "${HOTJAR_API_KEY}",
                "HOTJAR_SITE_ID": "${HOTJAR_SITE_ID}"
            },
            capabilities=[
                "get_heatmap", "create_heatmap", "list_heatmaps", "get_heatmap_data",
                "get_click_heatmap", "get_move_heatmap", "get_scroll_heatmap",
                "get_recording", "list_recordings", "search_recordings", "get_recording_events",
                "filter_recordings_by_page", "filter_recordings_by_user", "tag_recording",
                "create_survey", "update_survey", "publish_survey", "get_survey", "list_surveys",
                "get_survey_responses", "export_survey_results", "analyze_survey_sentiment",
                "create_feedback_widget", "update_feedback_widget", "get_feedback", "list_feedback",
                "get_incoming_feedback", "categorize_feedback", "respond_to_feedback",
                "create_poll", "launch_poll", "get_poll_results", "analyze_poll_data",
                "get_visitor_attributes", "identify_visitor", "get_visitor_sessions",
                "get_page_views", "get_form_analytics", "analyze_form_abandonment",
                "get_conversion_funnels", "create_funnel", "analyze_funnel_drop_offs",
                "create_dashboard", "get_dashboard", "share_dashboard",
                "export_data", "get_site_settings", "update_site_settings"
            ],
            description="Hotjar UX optimization platform - heatmaps, session recordings, surveys, feedback widgets, form analytics"
        ),
    }

    def __init__(self):
        self.running_servers: Dict[str, MCPClient] = {}  # Changed from subprocess.Popen to MCPClient
        self.server_outputs: Dict[str, List[str]] = {}
        self._lock = asyncio.Lock()

    def register_server(self, server: MCPServer) -> None:
        """Register a new MCP server"""
        self.SERVERS[server.name] = server
        logger.info(f"Registered MCP server: {server.name}")

    def unregister_server(self, name: str) -> bool:
        """Unregister an MCP server"""
        if name in self.SERVERS:
            del self.SERVERS[name]
            logger.info(f"Unregistered MCP server: {name}")
            return True
        return False

    async def start_server(self, name: str) -> bool:
        """Start an MCP server by name using MCPClient"""
        async with self._lock:
            if name not in self.SERVERS:
                logger.error(f"MCP server not found: {name}")
                return False

            if name in self.running_servers:
                logger.warning(f"MCP server already running: {name}")
                return True

            server = self.SERVERS[name]
            if not server.enabled:
                logger.warning(f"MCP server disabled: {name}")
                return False

            try:
                # Substitute environment variables in args
                args = []
                for arg in server.args:
                    if arg.startswith("${") and arg.endswith("}"):
                        # Handle default values: ${VAR:-default}
                        if ":-" in arg:
                            var_part, default = arg[2:-1].split(":-", 1)
                            args.append(os.getenv(var_part, default))
                        else:
                            args.append(os.getenv(arg[2:-1], ""))
                    else:
                        args.append(arg)

                # Convert registry MCPTransport to protocol MCPTransport
                if server.transport == MCPTransport.STDIO:
                    transport = ProtocolMCPTransport.STDIO
                elif server.transport == MCPTransport.HTTP or server.transport == MCPTransport.SSE:
                    transport = ProtocolMCPTransport.HTTP
                else:
                    transport = ProtocolMCPTransport.STDIO  # Default

                # Create MCPClient configuration
                config = MCPServerConfig(
                    name=server.name,
                    transport=transport,
                    command=server.command,
                    args=args,
                    env=server.get_env(),
                    url=f"http://localhost:{server.port}" if server.port else None,
                    timeout_seconds=60.0  # Increased timeout for npm package downloads on first run
                )

                # Create and connect MCPClient
                client = MCPClient(config)
                await client.connect()  # This will initialize and fetch tools

                self.running_servers[name] = client
                self.server_outputs[name] = []

                logger.info(f"Started MCP server: {name} ({len(client.get_tools())} tools available)")
                return True

            except Exception as e:
                logger.error(f"Failed to start MCP server {name}: {e}")
                return False

    async def stop_server(self, name: str) -> bool:
        """Stop a running MCP server"""
        async with self._lock:
            if name not in self.running_servers:
                return False

            client = self.running_servers[name]
            try:
                # Disconnect MCPClient (this will terminate the subprocess if STDIO)
                await client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting MCP server {name}: {e}")

            del self.running_servers[name]
            if name in self.server_outputs:
                del self.server_outputs[name]

            logger.info(f"Stopped MCP server: {name}")
            return True

    async def stop_all(self) -> None:
        """Stop all running MCP servers"""
        for name in list(self.running_servers.keys()):
            await self.stop_server(name)

    def is_running(self, name: str) -> bool:
        """Check if a server is running"""
        if name not in self.running_servers:
            return False
        client = self.running_servers[name]
        return client._connected  # Check if MCPClient is connected

    def list_available(self) -> List[Dict[str, Any]]:
        """List all available MCP servers"""
        return [
            {
                "name": name,
                "display_name": server.display_name,
                "description": server.description,
                "capabilities": server.capabilities,
                "transport": server.transport.value,
                "enabled": server.enabled,
                "running": self.is_running(name),
            }
            for name, server in self.SERVERS.items()
        ]

    def list_running(self) -> List[Dict[str, Any]]:
        """List running MCP servers"""
        return [
            {
                "name": name,
                "display_name": self.SERVERS[name].display_name,
                "pid": proc.pid,
                "capabilities": self.SERVERS[name].capabilities,
            }
            for name, proc in self.running_servers.items()
            if proc.poll() is None
        ]

    def get_server(self, name: str) -> Optional[MCPServer]:
        """Get server configuration by name"""
        return self.SERVERS.get(name)

    async def call_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on an MCP server using MCPClient.

        The MCPClient handles all transport details (STDIO, HTTP, WebSocket)
        and implements proper MCP protocol (initialize, tools/list, tools/call).
        """
        if server_name not in self.running_servers:
            # Auto-start server if not running
            if not await self.start_server(server_name):
                return {"error": f"Failed to start server: {server_name}"}

        client = self.running_servers[server_name]

        try:
            # Use MCPClient's call_tool method (handles all transports)
            result = await client.call_tool(tool_name, arguments)
            return result
        except Exception as e:
            logger.error(f"Error calling tool {tool_name} on {server_name}: {e}")
            return {"error": str(e)}

    # Note: _call_stdio() and _call_http() removed - MCPClient handles all transports


# Global registry instance
mcp_registry = MCPRegistry()
