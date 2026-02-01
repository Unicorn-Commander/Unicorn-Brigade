"""
Integrations Module

External service integrations for Unicorn Brigade agents.

Includes:
- Slack: Chat, channels, users, reactions, files
- Google Workspace: Gmail (send, read, search), Calendar (events, availability)
- Langflow: Visual workflow builder integration
- HuggingFace: Medical AI models (NER, image analysis, text generation)
"""

from app.integrations.slack import SlackClient, get_slack_client
from app.integrations.google_email import (
    GoogleEmailClient,
    get_client as get_google_email_client,
    send_email as google_send_email,
    get_email as google_get_email,
    list_emails as google_list_emails,
    search_emails as google_search_emails,
)
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
from app.integrations.langflow import (
    LangflowClient,
    LangflowFlow,
    LangflowError,
    LangflowAPIError,
    get_langflow_client,
    close_langflow_client,
)
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
