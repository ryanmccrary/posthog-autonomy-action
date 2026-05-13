from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class PostHogClient:
    """Wrapper around PostHog REST API for reading project state and creating resources."""

    def __init__(self, api_key: str, host: str, project_id: str) -> None:
        self._project_id = project_id
        self._client = httpx.Client(
            base_url=host.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    @property
    def _env_url(self) -> str:
        return f"/api/environments/{self._project_id}"

    @property
    def _project_url(self) -> str:
        return f"/api/projects/{self._project_id}"

    # --- Read operations ---

    def list_event_definitions(self, limit: int = 200) -> list[dict[str, Any]]:
        """Fetch existing event definitions for the project."""
        resp = self._client.get(
            f"{self._env_url}/event_definitions/",
            params={"limit": limit},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def list_property_definitions(self, limit: int = 200) -> list[dict[str, Any]]:
        """Fetch existing property definitions for the project."""
        resp = self._client.get(
            f"{self._env_url}/property_definitions/",
            params={"limit": limit},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def list_insights(self, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch existing insights (to check naming conventions and avoid duplicates)."""
        resp = self._client.get(
            f"{self._env_url}/insights/",
            params={"limit": limit, "saved": True},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def list_feature_flags(self, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch existing feature flags."""
        resp = self._client.get(
            f"{self._env_url}/feature_flags/",
            params={"limit": limit},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def list_dashboards(self, limit: int = 100) -> list[dict[str, Any]]:
        """Fetch existing dashboards."""
        resp = self._client.get(
            f"{self._env_url}/dashboards/",
            params={"limit": limit},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def list_integrations(self, kind: str = "slack") -> list[dict[str, Any]]:
        """Fetch integrations (e.g., Slack)."""
        resp = self._client.get(
            f"{self._env_url}/integrations/",
            params={"kind": kind},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    def list_integration_channels(self, integration_id: int) -> list[dict[str, Any]]:
        """Fetch channels for a Slack integration."""
        resp = self._client.get(
            f"{self._env_url}/integrations/{integration_id}/channels/",
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

    # --- Write operations ---

    def create_insight(
        self,
        name: str,
        description: str,
        query: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new insight."""
        resp = self._client.post(
            f"{self._env_url}/insights/",
            json={
                "name": name,
                "description": f"{description}\n\nCreated by PostHog Product Autonomy bot.",
                "query": query,
                "saved": True,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def create_dashboard(
        self,
        name: str,
        description: str,
        tiles: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a new dashboard."""
        payload: dict[str, Any] = {
            "name": name,
            "description": f"{description}\n\nCreated by PostHog Product Autonomy bot.",
        }
        if tiles:
            payload["tiles"] = tiles
        resp = self._client.post(
            f"{self._env_url}/dashboards/",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    def add_insight_to_dashboard(self, dashboard_id: int, insight_id: int) -> None:
        """Add an existing insight to a dashboard."""
        resp = self._client.patch(
            f"{self._env_url}/insights/{insight_id}/",
            json={"dashboards": [dashboard_id]},
        )
        resp.raise_for_status()

    def create_feature_flag(
        self,
        key: str,
        name: str,
        rollout_percentage: int = 0,
    ) -> dict[str, Any]:
        """Create a new feature flag."""
        resp = self._client.post(
            f"{self._env_url}/feature_flags/",
            json={
                "key": key,
                "name": f"{name} (Created by PostHog Product Autonomy bot)",
                "active": True,
                "filters": {
                    "groups": [
                        {
                            "rollout_percentage": rollout_percentage,
                            "properties": [],
                        }
                    ],
                },
            },
        )
        resp.raise_for_status()
        return resp.json()

    def create_annotation(self, content: str, date_marker: str) -> dict[str, Any]:
        """Create an annotation."""
        resp = self._client.post(
            f"{self._project_url}/annotations/",
            json={
                "content": content,
                "date_marker": date_marker,
                "scope": "project",
            },
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()
