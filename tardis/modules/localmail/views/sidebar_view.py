from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QWidget
from PySide6.QtCore import Qt, Signal, Slot
from noco_lib.noco_core.client import NocoClient
from app_core.sidebar.tree_model import SidebarNode, build_localmail_tree
import qtawesome as qta
import logging
from app_core.concurrency import run_async

class SidebarTreeView(QTreeWidget):
    node_selected = Signal(object)  # Emite el objeto SidebarNode seleccionado

    def __init__(self, main_window: QWidget, client: NocoClient, mailboxes: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self.main_window = main_window
        self.client = client
        self.mailboxes = mailboxes

        self._init_ui()
        self.populate_tree()

    def _init_ui(self) -> None:
        self.setHeaderHidden(True)
        self.setIndentation(12)
        self.setAnimated(True)
        
        # Estilos visuales a juego con el tema oscuro
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #18181b;
                color: #e1e1e6;
                border: 1px solid #27272a;
                border-radius: 6px;
                padding: 5px;
            }
            QTreeWidget::item {
                padding: 6px;
                border-radius: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #27272a;
            }
            QTreeWidget::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
        """)
        
        self.itemClicked.connect(self._on_item_clicked)

    def populate_tree(self) -> None:
        self.clear()
        
        # 1. Construir árbol del módulo localmail
        localmail_root = build_localmail_tree(self.mailboxes)
        for child in localmail_root.children:
            self._add_node_to_tree(child, self.invisibleRootItem())
            
        # 2. Agregar nodos adicionales contribuidos por otros módulos
        extra_nodes = getattr(self.main_window, "_extra_sidebar_nodes", [])
        for node in extra_nodes:
            self._add_node_to_tree(node, self.invisibleRootItem())
            
        # Expandir los nodos de primer nivel por defecto
        for i in range(self.topLevelItemCount()):
            self.topLevelItem(i).setExpanded(True)

    def _add_node_to_tree(self, node: SidebarNode, parent_item: QTreeWidgetItem) -> QTreeWidgetItem:
        item = QTreeWidgetItem(parent_item)
        item.setText(0, node.label)
        
        # Guardar ID y nodo completo en UserRole y UserRole+1
        item.setData(0, Qt.UserRole, node.id)
        item.setData(0, Qt.UserRole + 1, node)
        
        # Aplicar el icono si está disponible
        if node.icon:
            try:
                icon = qta.icon(node.icon, color='#e1e1e6')
                item.setIcon(0, icon)
            except Exception as e:
                logging.getLogger("tardis").warning("No se pudo cargar el icono %s: %s", node.icon, str(e))
                
        # Procesar hijos de forma recursiva
        for child in node.children:
            self._add_node_to_tree(child, item)
            
        return item

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        node = item.data(0, Qt.UserRole + 1)
        if node:
            self.node_selected.emit(node)

    def refresh_unread_counts(self, client: NocoClient, main_window: QWidget) -> None:
        """
        Para cada nodo del tipo 'inbox', consulta de manera asíncrona la cantidad de correos no leídos.
        """
        inbox_items = []
        
        # Búsqueda recursiva de ítems de tipo inbox
        def find_inbox_items(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                node = child.data(0, Qt.UserRole + 1)
                if node and node.folder == "inbox":
                    inbox_items.append((child, node))
                find_inbox_items(child)
                
        find_inbox_items(self.invisibleRootItem())
        
        from modules.localmail import service
        
        for item, node in inbox_items:
            # Closure para asociar correctamente el ítem y el nodo al callback
            def make_callback(target_item=item, target_node=node):
                def callback(result):
                    if result.success:
                        target_node.badge_count = result.affected_count
                    else:
                        target_node.badge_count = None
                        
                    badge = target_node.badge_count
                    if badge is not None and badge > 0:
                        target_item.setText(0, f"{target_node.label} ({badge})")
                    else:
                        target_item.setText(0, target_node.label)
                return callback
                
            run_async(
                service.list_inbox,
                client,
                node.mailboxes,
                folder="inbox",
                only_unread=True,
                on_success=make_callback()
            )

    def find_item_by_id(self, node_id: str) -> QTreeWidgetItem | None:
        def search(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                child_id = child.data(0, Qt.UserRole)
                if child_id == node_id:
                    return child
                result = search(child)
                if result:
                    return result
            return None
        return search(self.invisibleRootItem())

    def select_node_by_id(self, node_id: str) -> bool:
        item = self.find_item_by_id(node_id)
        if item:
            self.setCurrentItem(item)
            node = item.data(0, Qt.UserRole + 1)
            if node:
                self.node_selected.emit(node)
                return True
        return False

