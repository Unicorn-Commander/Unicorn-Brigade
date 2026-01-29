"""
A2UI (Agent-to-User Interface) Protocol Implementation

Google's open standard for agent-driven interfaces.
https://a2ui.org/
https://github.com/google/A2UI

Key concepts:
- Declarative UI: Agents describe UI, clients render native widgets
- Security: No arbitrary code execution, only approved component catalog
- Streaming: Incremental UI updates for responsive experience
- Framework-agnostic: Works with React, Flutter, SwiftUI, etc.
"""

from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class A2UIComponentType(str, Enum):
    """Standard A2UI component types"""
    # Layout
    CONTAINER = "container"
    ROW = "row"
    COLUMN = "column"
    CARD = "card"
    DIVIDER = "divider"

    # Text
    TEXT = "text"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    CODE = "code"
    MARKDOWN = "markdown"

    # Input
    BUTTON = "button"
    TEXT_FIELD = "textField"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    SELECT = "select"
    SLIDER = "slider"
    DATE_PICKER = "datePicker"

    # Display
    IMAGE = "image"
    ICON = "icon"
    BADGE = "badge"
    PROGRESS = "progress"
    CHART = "chart"
    TABLE = "table"

    # Feedback
    ALERT = "alert"
    TOAST = "toast"
    DIALOG = "dialog"
    LOADING = "loading"

    # Custom
    CUSTOM = "custom"


class A2UIAction(BaseModel):
    """Action that can be triggered from UI"""
    id: str
    type: str  # "submit", "navigate", "dismiss", "custom"
    payload: Dict[str, Any] = Field(default_factory=dict)


class A2UIComponent(BaseModel):
    """
    A2UI Component - Declarative UI element.

    The agent generates these; the client renders native widgets.
    """
    id: str
    type: A2UIComponentType
    properties: Dict[str, Any] = Field(default_factory=dict)
    children: List[str] = Field(default_factory=list)  # Child component IDs
    actions: List[A2UIAction] = Field(default_factory=list)
    data_binding: Optional[str] = None  # Reference to data model field


class A2UIDataModel(BaseModel):
    """Data model for A2UI interface"""
    fields: Dict[str, Any] = Field(default_factory=dict)
    validation: Dict[str, Any] = Field(default_factory=dict)


class A2UIResponse(BaseModel):
    """
    Complete A2UI response from agent to client.

    This is what gets sent over the wire.
    """
    version: str = "0.8"
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Components
    components: List[A2UIComponent] = Field(default_factory=list)
    root_id: Optional[str] = None  # Root component ID

    # Data
    data_model: A2UIDataModel = Field(default_factory=A2UIDataModel)

    # Streaming
    is_incremental: bool = False
    updates: List[Dict[str, Any]] = Field(default_factory=list)

    # Metadata
    agent_id: Optional[str] = None
    session_id: Optional[str] = None


class A2UIBuilder:
    """
    Builder for creating A2UI responses.

    Used by agents to construct UI descriptions.
    """

    def __init__(self, agent_id: Optional[str] = None):
        self.agent_id = agent_id
        self.components: Dict[str, A2UIComponent] = {}
        self.data_model = A2UIDataModel()
        self._id_counter = 0

    def _gen_id(self) -> str:
        """Generate unique component ID"""
        self._id_counter += 1
        return f"c_{self._id_counter}"

    def text(
        self,
        content: str,
        style: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a text component"""
        comp_id = self._gen_id()
        self.components[comp_id] = A2UIComponent(
            id=comp_id,
            type=A2UIComponentType.TEXT,
            properties={"content": content, "style": style or {}},
        )
        return comp_id

    def heading(
        self,
        content: str,
        level: int = 1,
    ) -> str:
        """Create a heading component"""
        comp_id = self._gen_id()
        self.components[comp_id] = A2UIComponent(
            id=comp_id,
            type=A2UIComponentType.HEADING,
            properties={"content": content, "level": level},
        )
        return comp_id

    def markdown(self, content: str) -> str:
        """Create a markdown component"""
        comp_id = self._gen_id()
        self.components[comp_id] = A2UIComponent(
            id=comp_id,
            type=A2UIComponentType.MARKDOWN,
            properties={"content": content},
        )
        return comp_id

    def card(
        self,
        title: Optional[str] = None,
        children: Optional[List[str]] = None,
    ) -> str:
        """Create a card component"""
        comp_id = self._gen_id()
        self.components[comp_id] = A2UIComponent(
            id=comp_id,
            type=A2UIComponentType.CARD,
            properties={"title": title},
            children=children or [],
        )
        return comp_id

    def button(
        self,
        label: str,
        action_type: str = "submit",
        payload: Optional[Dict[str, Any]] = None,
        variant: str = "primary",
    ) -> str:
        """Create a button component"""
        comp_id = self._gen_id()
        action_id = f"action_{comp_id}"

        self.components[comp_id] = A2UIComponent(
            id=comp_id,
            type=A2UIComponentType.BUTTON,
            properties={"label": label, "variant": variant},
            actions=[A2UIAction(
                id=action_id,
                type=action_type,
                payload=payload or {},
            )],
        )
        return comp_id

    def text_field(
        self,
        label: str,
        placeholder: str = "",
        data_field: Optional[str] = None,
        required: bool = False,
    ) -> str:
        """Create a text field component"""
        comp_id = self._gen_id()
        self.components[comp_id] = A2UIComponent(
            id=comp_id,
            type=A2UIComponentType.TEXT_FIELD,
            properties={
                "label": label,
                "placeholder": placeholder,
                "required": required,
            },
            data_binding=data_field,
        )
        return comp_id

    def table(
        self,
        columns: List[Dict[str, str]],
        data_field: str,
    ) -> str:
        """Create a table component"""
        comp_id = self._gen_id()
        self.components[comp_id] = A2UIComponent(
            id=comp_id,
            type=A2UIComponentType.TABLE,
            properties={"columns": columns},
            data_binding=data_field,
        )
        return comp_id

    def progress(
        self,
        value: float,
        label: Optional[str] = None,
    ) -> str:
        """Create a progress indicator"""
        comp_id = self._gen_id()
        self.components[comp_id] = A2UIComponent(
            id=comp_id,
            type=A2UIComponentType.PROGRESS,
            properties={"value": value, "label": label},
        )
        return comp_id

    def alert(
        self,
        message: str,
        severity: str = "info",  # "info", "warning", "error", "success"
    ) -> str:
        """Create an alert component"""
        comp_id = self._gen_id()
        self.components[comp_id] = A2UIComponent(
            id=comp_id,
            type=A2UIComponentType.ALERT,
            properties={"message": message, "severity": severity},
        )
        return comp_id

    def column(self, children: List[str], gap: int = 8) -> str:
        """Create a column layout"""
        comp_id = self._gen_id()
        self.components[comp_id] = A2UIComponent(
            id=comp_id,
            type=A2UIComponentType.COLUMN,
            properties={"gap": gap},
            children=children,
        )
        return comp_id

    def row(self, children: List[str], gap: int = 8) -> str:
        """Create a row layout"""
        comp_id = self._gen_id()
        self.components[comp_id] = A2UIComponent(
            id=comp_id,
            type=A2UIComponentType.ROW,
            properties={"gap": gap},
            children=children,
        )
        return comp_id

    def set_data(self, field: str, value: Any):
        """Set a field in the data model"""
        self.data_model.fields[field] = value

    def build(self, root_id: Optional[str] = None) -> A2UIResponse:
        """Build the complete A2UI response"""
        return A2UIResponse(
            components=list(self.components.values()),
            root_id=root_id or (list(self.components.keys())[-1] if self.components else None),
            data_model=self.data_model,
            agent_id=self.agent_id,
        )


class A2UIRenderer:
    """
    Client-side A2UI renderer.

    Maps A2UI components to native widgets.
    This would be implemented in the Unicorn Squad desktop client.
    """

    def __init__(self, component_catalog: Optional[Dict[str, Any]] = None):
        """
        Initialize renderer with component catalog.

        The catalog maps A2UI types to native widget implementations.
        """
        self.catalog = component_catalog or self._default_catalog()

    def _default_catalog(self) -> Dict[str, Any]:
        """Default component catalog (for CLI/text rendering)"""
        return {
            A2UIComponentType.TEXT: self._render_text,
            A2UIComponentType.HEADING: self._render_heading,
            A2UIComponentType.MARKDOWN: self._render_markdown,
            A2UIComponentType.CARD: self._render_card,
            A2UIComponentType.BUTTON: self._render_button,
            A2UIComponentType.ALERT: self._render_alert,
            A2UIComponentType.TABLE: self._render_table,
            A2UIComponentType.PROGRESS: self._render_progress,
        }

    def render(self, response: A2UIResponse) -> str:
        """Render A2UI response to text (CLI output)"""
        if not response.root_id:
            return ""

        components_by_id = {c.id: c for c in response.components}
        return self._render_component(
            components_by_id.get(response.root_id),
            components_by_id,
            response.data_model,
        )

    def _render_component(
        self,
        component: Optional[A2UIComponent],
        components: Dict[str, A2UIComponent],
        data: A2UIDataModel,
    ) -> str:
        """Recursively render a component"""
        if not component:
            return ""

        renderer = self.catalog.get(component.type, self._render_default)
        content = renderer(component, data)

        # Render children
        if component.children:
            child_content = "\n".join(
                self._render_component(components.get(cid), components, data)
                for cid in component.children
            )
            content = f"{content}\n{child_content}"

        return content

    def _render_text(self, comp: A2UIComponent, data: A2UIDataModel) -> str:
        return comp.properties.get("content", "")

    def _render_heading(self, comp: A2UIComponent, data: A2UIDataModel) -> str:
        level = comp.properties.get("level", 1)
        prefix = "#" * level
        return f"{prefix} {comp.properties.get('content', '')}"

    def _render_markdown(self, comp: A2UIComponent, data: A2UIDataModel) -> str:
        return comp.properties.get("content", "")

    def _render_card(self, comp: A2UIComponent, data: A2UIDataModel) -> str:
        title = comp.properties.get("title", "")
        return f"┌─ {title} ─┐" if title else "┌────────┐"

    def _render_button(self, comp: A2UIComponent, data: A2UIDataModel) -> str:
        label = comp.properties.get("label", "Button")
        return f"[{label}]"

    def _render_alert(self, comp: A2UIComponent, data: A2UIDataModel) -> str:
        severity = comp.properties.get("severity", "info")
        message = comp.properties.get("message", "")
        icons = {"info": "ℹ", "warning": "⚠", "error": "✗", "success": "✓"}
        return f"{icons.get(severity, 'ℹ')} {message}"

    def _render_table(self, comp: A2UIComponent, data: A2UIDataModel) -> str:
        columns = comp.properties.get("columns", [])
        headers = " | ".join(c.get("header", c.get("field", "")) for c in columns)
        return f"| {headers} |"

    def _render_progress(self, comp: A2UIComponent, data: A2UIDataModel) -> str:
        value = comp.properties.get("value", 0)
        filled = int(value * 20)
        bar = "█" * filled + "░" * (20 - filled)
        return f"[{bar}] {int(value * 100)}%"

    def _render_default(self, comp: A2UIComponent, data: A2UIDataModel) -> str:
        return f"<{comp.type.value}>"


# Helper functions for quick UI generation

def task_progress_ui(
    task_id: str,
    status: str,
    progress: float,
    current_step: str,
    agent_id: Optional[str] = None,
) -> A2UIResponse:
    """Generate standard task progress UI"""
    builder = A2UIBuilder(agent_id)

    heading = builder.heading(f"Task: {task_id}", level=2)
    status_badge = builder.text(f"Status: {status}")
    progress_bar = builder.progress(progress, current_step)

    card = builder.card(
        title="Task Progress",
        children=[heading, status_badge, progress_bar],
    )

    return builder.build(card)


def approval_request_ui(
    step_description: str,
    risk_level: str,
    artifacts: List[str],
    token_id: str,
    agent_id: Optional[str] = None,
) -> A2UIResponse:
    """Generate approval request UI"""
    builder = A2UIBuilder(agent_id)

    heading = builder.heading("Approval Required", level=2)

    risk_alert = builder.alert(
        f"Risk Level: {risk_level.upper()}",
        severity="warning" if risk_level == "medium" else "error" if risk_level == "high" else "info"
    )

    description = builder.text(step_description)

    if artifacts:
        artifacts_text = builder.text(f"Pending artifacts: {', '.join(artifacts)}")
    else:
        artifacts_text = None

    approve_btn = builder.button(
        "Approve",
        action_type="submit",
        payload={"token_id": token_id, "approved": True},
        variant="primary",
    )

    reject_btn = builder.button(
        "Reject",
        action_type="submit",
        payload={"token_id": token_id, "approved": False},
        variant="danger",
    )

    button_row = builder.row([approve_btn, reject_btn])

    children = [heading, risk_alert, description]
    if artifacts_text:
        children.append(artifacts_text)
    children.append(button_row)

    card = builder.card(title=None, children=children)

    return builder.build(card)
