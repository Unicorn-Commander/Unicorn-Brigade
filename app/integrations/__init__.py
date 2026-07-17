"""
Integrations Module

External service integrations for Unicorn Brigade agents.

Includes:
- Slack: Chat, channels, users, reactions, files
- Google Workspace: Gmail (send, read, search), Calendar (events, availability)
- Langflow: Visual workflow builder integration
- HuggingFace: Medical AI models (NER, image analysis, text generation)

Optional-integration re-exports are LAZY/GUARDED (each wrapped in try/except):
each integration's SDK (slack_sdk, google-auth, etc.) is an OPTIONAL dependency,
so importing this package — e.g. to reach the lightweight, dependency-free
billing modules ``app.integrations.lago`` / ``app.integrations.metering`` /
``app.integrations.ops_center_billing`` (httpx + app.db only) — must NOT hard-
fail merely because an unrelated integration's SDK isn't installed. A missing
SDK leaves that integration's names bound to ``None`` (import of the package
still succeeds); the integration's own module raises clearly if actually used.
This also lets the BR-3 billing proof import the metering seam under a minimal
interpreter (no slack_sdk/google/hf) exactly like the RLS proof imports app.db.
"""
import logging as _logging

_log = _logging.getLogger(__name__)

# Names are defined regardless so ``from app.integrations import X`` never
# NameErrors; a guarded import overwrites them when the SDK is present.
SlackClient = get_slack_client = None
GoogleEmailClient = get_google_email_client = None
google_send_email = google_get_email = google_list_emails = google_search_emails = None
google_calendar = None
GoogleCalendarClient = get_google_calendar_client = google_calendar_enabled = None
google_create_event = google_get_event = google_list_events = None
google_update_event = google_delete_event = google_get_free_busy = google_find_available_slots = None
LangflowClient = LangflowFlow = LangflowError = LangflowAPIError = None
get_langflow_client = close_langflow_client = None
HuggingFaceClient = MedicalAnalyzer = get_huggingface_client = get_medical_analyzer = None
close_huggingface_clients = list_medical_models = huggingface_enabled = None
MEDICAL_MODELS = MODEL_CATEGORIES = IMAGE_MODALITIES = None
HuggingFaceError = HuggingFaceAPIError = HuggingFaceRateLimitError = None
HuggingFaceTimeoutError = HuggingFaceConnectionError = None

try:
    from app.integrations.slack import SlackClient, get_slack_client
except Exception as _e:  # noqa: BLE001 — optional SDK (slack_sdk) may be absent
    _log.debug("app.integrations.slack unavailable: %s", _e)

try:
    from app.integrations.google_email import (
        GoogleEmailClient,
        get_client as get_google_email_client,
        send_email as google_send_email,
        get_email as google_get_email,
        list_emails as google_list_emails,
        search_emails as google_search_emails,
    )
except Exception as _e:  # noqa: BLE001
    _log.debug("app.integrations.google_email unavailable: %s", _e)

try:
    from app.integrations import google_calendar
    from app.integrations.google_calendar import (
        GoogleCalendarClient,
        get_client as get_google_calendar_client,
        is_enabled as google_calendar_enabled,
        create_event as google_create_event,
        get_event as google_get_event,
        list_events as google_list_events,
        update_event as google_update_event,
        delete_event as google_delete_event,
        get_free_busy as google_get_free_busy,
        find_available_slots as google_find_available_slots,
    )
except Exception as _e:  # noqa: BLE001
    _log.debug("app.integrations.google_calendar unavailable: %s", _e)

try:
    from app.integrations.langflow import (
        LangflowClient,
        LangflowFlow,
        LangflowError,
        LangflowAPIError,
        get_langflow_client,
        close_langflow_client,
    )
except Exception as _e:  # noqa: BLE001
    _log.debug("app.integrations.langflow unavailable: %s", _e)

try:
    from app.integrations.huggingface import (
        HuggingFaceClient,
        MedicalAnalyzer,
        get_huggingface_client,
        get_medical_analyzer,
        close_clients as close_huggingface_clients,
        list_medical_models,
        is_enabled as huggingface_enabled,
        MEDICAL_MODELS,
        MODEL_CATEGORIES,
        IMAGE_MODALITIES,
        HuggingFaceError,
        HuggingFaceAPIError,
        HuggingFaceRateLimitError,
        HuggingFaceTimeoutError,
        HuggingFaceConnectionError,
    )
except Exception as _e:  # noqa: BLE001
    _log.debug("app.integrations.huggingface unavailable: %s", _e)

__all__ = [
    # Slack
    "SlackClient",
    "get_slack_client",
    # Google Email
    "GoogleEmailClient",
    "get_google_email_client",
    "google_send_email",
    "google_get_email",
    "google_list_emails",
    "google_search_emails",
    # Google Calendar
    "google_calendar",
    "GoogleCalendarClient",
    "get_google_calendar_client",
    "google_calendar_enabled",
    "google_create_event",
    "google_get_event",
    "google_list_events",
    "google_update_event",
    "google_delete_event",
    "google_get_free_busy",
    "google_find_available_slots",
    # Langflow
    "LangflowClient",
    "LangflowFlow",
    "LangflowError",
    "LangflowAPIError",
    "get_langflow_client",
    "close_langflow_client",
    # HuggingFace Medical AI
    "HuggingFaceClient",
    "MedicalAnalyzer",
    "get_huggingface_client",
    "get_medical_analyzer",
    "close_huggingface_clients",
    "list_medical_models",
    "huggingface_enabled",
    "MEDICAL_MODELS",
    "MODEL_CATEGORIES",
    "IMAGE_MODALITIES",
    "HuggingFaceError",
    "HuggingFaceAPIError",
    "HuggingFaceRateLimitError",
    "HuggingFaceTimeoutError",
    "HuggingFaceConnectionError",
]
