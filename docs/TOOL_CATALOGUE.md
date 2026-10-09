# Built-in tool catalogue

`app.llm.tool_resolver.TOOL_REGISTRY` is the executable source of truth. Migration
`20261009_01_tool_catalogue_complete` seeds every current built-in name, including
names from optional integrations. The migration uses `ON CONFLICT DO NOTHING` so
an operator's reviewed catalogue values survive a later startup.

Permission levels are ordered from 1 (lowest) to 5 (highest). The execution guard
refuses a registered tool whose catalogue row is absent by default. Set
`BRIGADE_TOOL_CATALOG_FAIL_CLOSED=false` only for a single restart while repairing
a late seed; it restores the legacy level-1 fallback.

The two historical rows `agentic_rag` and `knowledge_graph` are retained for
metadata compatibility but are not executable registry entries.

To audit existing agent records without changing them, run
`./.venv/bin/python scripts/report_unknown_agent_tools.py`. It reports only
records whose stored names do not resolve in the current executable registry.

| tool | level | rationale |
| --- | ---: | --- |
| `add_task_comment` | 5 | external Project Ops posting |
| `analytics_sql` | 1 | read-only analytics query |
| `bmc_event_log` | 1 | read-only hardware event inspection |
| `bmc_flash_firmware` | 5 | destructive firmware mutation |
| `bmc_get_firmware` | 1 | read-only firmware inspection |
| `bmc_get_info` | 1 | read-only hardware health inspection |
| `bmc_get_power` | 1 | read-only power inspection |
| `bmc_get_thermal` | 1 | read-only thermal inspection |
| `bmc_list_targets` | 1 | read-only target inventory |
| `bmc_power_control` | 5 | destructive hardware power control |
| `browser` | 5 | browser automation can mutate external state |
| `calculator` | 1 | calculation only |
| `canvas_create` | 5 | external canvas posting |
| `canvas_edit` | 5 | external canvas posting |
| `canvas_rewrite` | 5 | external canvas replacement |
| `cdr_deep_research` | 4 | paid/fan-out research retained at its stricter historical tier |
| `cdr_quick_answer` | 1 | read-only search/research |
| `cdr_search` | 1 | read-only search |
| `code` | 2 | sandboxed code execution |
| `code_sandbox` | 2 | sandboxed code execution |
| `colonel_facts` | 1 | read-only fleet snapshot |
| `company` | 1 | read-only company lookup |
| `create_project` | 5 | external Project Ops mutation |
| `create_task` | 5 | external Project Ops mutation |
| `csv` | 1 | in-memory data utility |
| `data_analyze` | 1 | read-only data analysis |
| `database` | 4 | key-value database mutation retained at its stricter historical tier |
| `datetime` | 1 | read-only clock utility |
| `delegate_to_agent` | 5 | delegated execution can transitively invoke tools |
| `doc_generate` | 2 | internal generated artifact |
| `email` | 5 | outbound email |
| `file` | 5 | filesystem write/delete capability |
| `find_connections` | 1 | read-only graph traversal |
| `find_evidence_gaps` | 1 | read-only evidence analysis |
| `generate_pdf` | 2 | internal generated artifact |
| `get_case_summary` | 1 | read-only case lookup |
| `get_document` | 1 | read-only document metadata lookup |
| `get_document_content` | 1 | read-only document content lookup |
| `get_entity` | 1 | read-only entity lookup |
| `get_evidence_folders` | 1 | read-only evidence inventory |
| `get_project` | 1 | read-only Project Ops lookup |
| `get_recent_activity` | 1 | read-only Project Ops activity lookup |
| `get_relationships` | 1 | read-only relationship lookup |
| `get_strategy` | 1 | read-only case strategy lookup |
| `get_timeline` | 1 | read-only timeline lookup |
| `glitter_add_allergy` | 3 | sensitive medical record mutation |
| `glitter_add_appointment` | 3 | sensitive medical record mutation |
| `glitter_add_care_plan_item` | 3 | sensitive medical record mutation |
| `glitter_add_condition` | 3 | sensitive medical record mutation |
| `glitter_add_medication` | 3 | sensitive medical record mutation |
| `glitter_add_vital` | 3 | sensitive medical record mutation |
| `glitter_ask` | 3 | sensitive PHI consultation |
| `glitter_get_health_summary` | 3 | sensitive PHI read |
| `glitter_get_timeline` | 3 | sensitive PHI read |
| `glitter_get_visit_summary` | 3 | sensitive PHI read |
| `glitter_ingest_text` | 3 | sensitive medical record mutation |
| `glitter_list_allergies` | 3 | sensitive PHI read |
| `glitter_list_conditions` | 3 | sensitive PHI read |
| `glitter_list_labs` | 3 | sensitive PHI read |
| `glitter_list_medications` | 3 | sensitive PHI read |
| `glitter_list_models` | 1 | read-only model registry lookup |
| `glitter_list_vitals` | 3 | sensitive PHI read |
| `ha_call_service` | 5 | home-device control |
| `ha_get_entity_state` | 1 | read-only home state lookup |
| `ha_get_history` | 1 | read-only home history lookup |
| `ha_get_services` | 1 | read-only home service inventory |
| `ha_list_areas` | 1 | read-only home area inventory |
| `ha_list_entities` | 1 | read-only home entity inventory |
| `ha_search_entities` | 1 | read-only home entity search |
| `http_request` | 5 | arbitrary outbound request and credential-bearing capability |
| `image` | 2 | paid generated artifact |
| `json` | 1 | in-memory data utility |
| `kg_query` | 2 | internal graph query/store utility |
| `knowledge_ops_ground` | 1 | read-only internal knowledge grounding |
| `knowledge_ops_save` | 2 | internal knowledge write |
| `knowledge_ops_search` | 1 | read-only internal knowledge search |
| `knowledge_query` | 1 | read-only knowledge graph query |
| `knowledge_store` | 3 | durable knowledge write retained at its stricter historical tier |
| `list_entities` | 1 | read-only case inventory |
| `list_my_projects` | 1 | read-only Project Ops lookup |
| `list_my_tasks` | 1 | read-only Project Ops lookup |
| `list_project_documents` | 1 | read-only Project Ops lookup |
| `memory` | 2 | internal memory write/read utility |
| `notify` | 5 | outbound notification |
| `pdf_extract` | 1 | read-only document extraction |
| `qrcode` | 1 | in-memory data utility |
| `rss` | 1 | read-only feed lookup |
| `sandbox_session` | 2 | sandbox/session mutation |
| `schedule` | 1 | in-memory scheduling utility |
| `screenshot` | 1 | read-only capture |
| `search_entities` | 1 | read-only case search |
| `search_evidence` | 1 | read-only evidence search |
| `search_knowledge` | 1 | read-only room knowledge search |
| `search_projects` | 1 | read-only Project Ops search |
| `shell` | 5 | shell execution and destructive system capability |
| `slack` | 5 | outbound Slack posting |
| `text` | 1 | in-memory text utility |
| `translate` | 1 | read-only translation request |
| `ucb_click` | 5 | browser interaction can submit external actions |
| `ucb_console_messages` | 1 | read-only browser diagnostics |
| `ucb_fill_form` | 5 | browser form submission capability |
| `ucb_navigate` | 1 | read-only browser navigation |
| `ucb_page_text` | 1 | read-only browser text |
| `ucb_pdf_save` | 2 | browser-host artifact write |
| `ucb_screenshot` | 1 | read-only browser capture |
| `ucb_snapshot` | 1 | read-only browser accessibility snapshot |
| `ucb_type` | 5 | browser interaction can submit external actions |
| `update_billing_fields` | 5 | external financial/project posting |
| `update_project_status` | 5 | external Project Ops mutation |
| `update_task_status` | 5 | external Project Ops mutation |
| `upload_document` | 5 | external Project Ops document posting |
| `url_preview` | 1 | read-only URL inspection |
| `weather` | 1 | read-only weather lookup |
| `web_search` | 1 | read-only web search |
