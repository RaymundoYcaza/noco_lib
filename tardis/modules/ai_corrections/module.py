"""module.py — AI Corrections module entry point for Tardis.

Registers a two-screen workflow (Setup → Review) as a nav item
in the App Switcher bar.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app_core.main_window import MainWindow
    from noco_lib.noco_core.client import NocoClient

from PySide6.QtWidgets import QStackedWidget

from ai_lib.ai_client import AIClient
from modules.ai_corrections.views.setup_view import SetupView
from modules.ai_corrections.views.review_view import ReviewView

import logging

logger = logging.getLogger("tardis")


def register(app: MainWindow, client: NocoClient) -> None:
    """Register the AI Corrections module as a navigation item.

    Creates a two-screen workflow inside a ``QStackedWidget``:
    index 0 = ``SetupView`` (configuration form), index 1 =
    ``ReviewView`` (comparison table with accept/reject). The
    screen switches automatically after AI processing completes.

    Parameters
    ----------
    app : MainWindow
        The Tardis main window.
    client : NocoClient
        NocoDB client for reading/writing table data.
    """
    # 1. Create the AI client from config
    ai_client = AIClient.from_config(app.config)

    # 2. Stacked widget holding the two screens
    screen = QStackedWidget()

    # 3. Setup screen (index 0)
    setup_view = SetupView(app.config, client, ai_client, app)
    screen.addWidget(setup_view)

    # 4. Placeholder for the review screen (created dynamically)
    review_view: ReviewView | None = None

    # 5. Signal wiring: analysis_ready → process → show review
    def on_analysis_ready(data: dict) -> None:
        """Start AI processing, then switch to ReviewView on completion."""
        setup_view.process_records(
            data,
            on_complete=lambda results: _show_review(results, data["table_id"]),
        )

    setup_view.analysis_ready.connect(on_analysis_ready)

    def _show_review(results: list[dict], table_id: str) -> None:
        """Create (or replace) the ReviewView and switch to it."""
        nonlocal review_view

        # Remove existing review widget if any (always at index 1)
        if review_view is not None:
            try:
                screen.removeWidget(review_view)
                review_view.deleteLater()
            except Exception:
                logger.exception("Error cleaning up old ReviewView")

        review_view = ReviewView(app, client, results, table_id)

        # Back button → return to setup screen
        review_view.back_requested.connect(lambda: screen.setCurrentIndex(0))

        screen.addWidget(review_view)
        screen.setCurrentIndex(1)

    # 6. Register with the nav bar
    app.register_nav_item(
        module_id="ai_corrections",
        icon="fa5s.magic",
        label="AI Corrections",
        widget=screen,
        position="middle",
    )

    logger.info("AI Corrections module registered (nav item)")
