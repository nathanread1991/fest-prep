"""Utility functions for web interface."""

import json
import os
from pathlib import Path
from typing import Dict, Optional


class AssetManager:
    """Manages asset URLs with cache busting and minification."""

    def __init__(self) -> None:
        self._manifest: Optional[Dict[str, str]] = None
        self._manifest_path = Path(__file__).parent / "static" / "manifest-assets.json"
        self._is_production = os.getenv("ENVIRONMENT", "development") == "production"

    def _load_manifest(self) -> Dict[str, str]:
        """Load asset manifest from file."""
        if self._manifest is None:
            try:
                if self._manifest_path.exists():
                    with open(self._manifest_path, "r") as f:
                        self._manifest = json.load(f)
                else:
                    self._manifest = {}
            except Exception:
                self._manifest = {}

        return self._manifest

    def asset_url(self, asset_path: str) -> str:
        """Get the URL for an asset with cache busting."""
        # Always use original files in development or if manifest doesn't exist
        if not self._is_production or not self._manifest_path.exists():
            return f"/static/{asset_path}"

        # In production, use minified and cache-busted files
        manifest = self._load_manifest()

        if asset_path in manifest:
            return f"/static/{manifest[asset_path]}"

        # Fallback to original path if not in manifest
        return f"/static/{asset_path}"

    def css_url(self, filename: str) -> str:
        """Get CSS file URL."""
        return self.asset_url(f"css/{filename}")

    def js_url(self, filename: str) -> str:
        """Get JavaScript file URL."""
        return self.asset_url(f"js/{filename}")


# Global asset manager instance
asset_manager = AssetManager()


def get_asset_url(asset_path: str) -> str:
    """Get asset URL with cache busting."""
    return asset_manager.asset_url(asset_path)


def get_css_url(filename: str) -> str:
    """Get CSS file URL."""
    return asset_manager.css_url(filename)


def get_js_url(filename: str) -> str:
    """Get JavaScript file URL."""
    return asset_manager.js_url(filename)
