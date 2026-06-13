from dataclasses import dataclass, field
from typing import Any

@dataclass
class SidebarNode:
    id: str                 # unique key, e.g. "all:inbox", "alicia.gentil@inorizonti.com:sent"
    label: str               # display text, e.g. "Inbox", "Sent"
    icon: str | None         # qtawesome icon name, e.g. "fa5s.inbox"
    node_type: str           # "mailbox" | "folder" | "module_root" | "module_item"
    mailboxes: list[str]     # which mailbox(es) this node queries (empty for module nodes)
    folder: str | None       # "inbox"|"sent"|"archive"|"trash"|"drafts"|None
    children: list["SidebarNode"] = field(default_factory=list)
    badge_count: int | None = None  # unread count, only for folder="inbox" nodes

def build_localmail_tree(mailboxes: list[str]) -> SidebarNode:
    """
    Construye y retorna la estructura del árbol para el módulo de correo.
    - El nodo raíz es virtual y contiene "All Mailboxes" y cada casilla individual.
    - Cada una de estas a su vez contiene las 5 carpetas básicas: Inbox, Sent, Archive, Trash, Drafts.
    """
    top_level_children = []

    # 1. Unified mailbox ("All Mailboxes")
    all_folders = [
        SidebarNode(id="all:inbox", label="Inbox", icon="fa5s.inbox", node_type="folder", mailboxes=mailboxes, folder="inbox"),
        SidebarNode(id="all:sent", label="Sent", icon="fa5s.paper-plane", node_type="folder", mailboxes=mailboxes, folder="sent"),
        SidebarNode(id="all:archive", label="Archive", icon="fa5s.archive", node_type="folder", mailboxes=mailboxes, folder="archive"),
        SidebarNode(id="all:trash", label="Trash", icon="fa5s.trash", node_type="folder", mailboxes=mailboxes, folder="trash"),
        SidebarNode(id="all:drafts", label="Drafts", icon="fa5s.file-alt", node_type="folder", mailboxes=mailboxes, folder="drafts"),
    ]
    all_node = SidebarNode(
        id="all",
        label="All Mailboxes",
        icon="fa5s.layer-group",
        node_type="mailbox",
        mailboxes=mailboxes,
        folder=None,
        children=all_folders
    )
    top_level_children.append(all_node)

    # 2. Individual mailboxes
    for m in mailboxes:
        m_folders = [
            SidebarNode(id=f"{m}:inbox", label="Inbox", icon="fa5s.inbox", node_type="folder", mailboxes=[m], folder="inbox"),
            SidebarNode(id=f"{m}:sent", label="Sent", icon="fa5s.paper-plane", node_type="folder", mailboxes=[m], folder="sent"),
            SidebarNode(id=f"{m}:archive", label="Archive", icon="fa5s.archive", node_type="folder", mailboxes=[m], folder="archive"),
            SidebarNode(id=f"{m}:trash", label="Trash", icon="fa5s.trash", node_type="folder", mailboxes=[m], folder="trash"),
            SidebarNode(id=f"{m}:drafts", label="Drafts", icon="fa5s.file-alt", node_type="folder", mailboxes=[m], folder="drafts"),
        ]
        m_node = SidebarNode(
            id=m,
            label=m,
            icon="fa5s.envelope",
            node_type="mailbox",
            mailboxes=[m],
            folder=None,
            children=m_folders
        )
        top_level_children.append(m_node)

    # Root virtual container node
    localmail_root = SidebarNode(
        id="localmail_root",
        label="LocalMail",
        icon=None,
        node_type="module_root",
        mailboxes=mailboxes,
        folder=None,
        children=top_level_children
    )
    return localmail_root
