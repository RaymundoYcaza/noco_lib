# Tardis Extension Points & Module Authoring Guide

This document summarizes the extension points available in the Tardis core application for future module authors.

## 1. UI Integration APIs (`MainWindow`)

The main window class (`MainWindow`) exposes several key methods to allow modules to integrate components into the main interface.

### Docking and Floating Windows

*   `MainWindow.add_dock_panel(widget: QWidget, title: str, area: str = "left") -> CDockWidget`
    Creates a dockable panel containing the provided widget and adds it to the central dock manager in the specified area (`"left"`, `"right"`, `"top"`, `"bottom"`, or `"center"`).
*   `MainWindow.add_floating_window(widget: QWidget, title: str) -> CDockWidget`
    Creates an independent floating window wrapping the provided widget. Features:
    *   **Custom Close Handling**: Automatically enabled on the floating dock wrapper to intercept titlebar closing and propagate it to the child widget via `close()`.
    *   **Geometry Persistence**: Automatically saves and restores the floating container's size and position from the QSettings key `floating/<title>/geometry` (or `floating/Compose/geometry` for `"Redactar correo"`).

### Menus, Toolbars, and Notifications

*   `MainWindow.add_menu_action(menu_path: str, label: str, callback: Callable) -> None`
    Adds an option to the main window's menu system using a nested route syntax, e.g. `"LocalMail > Redactar"`.
*   `MainWindow.add_toolbar_action(icon_or_text, label: str, callback: Callable) -> None`
    Adds an action button to the application toolbar (reserved for global shortcuts).
*   `MainWindow.show_notification(text: str, level: str = "info", duration_ms: int = 4000) -> None`
    Displays a modern, animated "Toast" notification in the bottom right corner of the application window. Supported levels are `"success"`, `"info"`, `"warning"`, and `"error"`.

---

## 2. Sidebar Integration & Ordering Requirements

Modules can add custom items to the main left navigation sidebar.

### SidebarNode Structure

The sidebar uses a tree structure populated with `SidebarNode` objects:

```python
@dataclass
class SidebarNode:
    id: str                 # Unique key, e.g. "all:inbox", "custom_module_root"
    label: str               # Display text shown in the sidebar
    icon: str | None         # QtAwesome icon identifier, e.g. "fa5s.inbox"
    node_type: str           # "mailbox" | "folder" | "module_root" | "module_item"
    mailboxes: list[str]     # List of mailboxes queried (empty for non-mail nodes)
    folder: str | None       # Target folder ("inbox", "sent", etc., or None)
    children: list["SidebarNode"] = field(default_factory=list)
    badge_count: int | None = None  # Optional unread count badge
```

### Adding a Sidebar Node

To add a sidebar node, use:
```python
MainWindow.add_sidebar_node(node: SidebarNode)
```

> [!IMPORTANT]
> **Registration Ordering Requirement**:
> `add_sidebar_node` MUST be called inside the module's `register(app, client)` function *before* the main sidebar tree structure is constructed. The main application builds the tree model after module registration is complete.

---

## 3. Logging & Exception Conventions

To ensure stability, modules must catch all exceptions within Qt slot functions and prevent crashes from propagating to the global handler:

*   **Convention**: Inside any Qt slot that could raise, use a `try-except` block and log the exception with `logging.getLogger("tardis").exception(...)`.
*   **Example**:
    ```python
    def on_button_clicked(self) -> None:
        try:
            # Dangerous Qt/business logic
            ...
        except Exception as e:
            logging.getLogger("tardis").exception("Error during button action execution")
    ```

---

## 4. Sending Notifications via LocalMail

Any module requiring the ability to dispatch notifications to the LocalMail inbox should use the helper functions in `modules/localmail/service.py`:

*   **Notify API**: Use `service.notify(client, to_user, subject, body, priority)` to dynamically create a message entry under the `"inbox"` folder of a specific recipient user in NocoDB.
*   **Example**:
    ```python
    from modules.localmail import service
    
    service.notify(
        client=noco_client,
        to_user="alice.gentil@inorizonti.com",
        subject="System Alert",
        body="A critical event has occurred in the backup process.",
        priority="Alta"
    )
    ```
