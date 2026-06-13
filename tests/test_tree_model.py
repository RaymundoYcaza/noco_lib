import sys
from pathlib import Path

# Add paths to sys.path
root_dir = Path(__file__).resolve().parent.parent
tardis_dir = root_dir / "tardis"
if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))

from app_core.sidebar.tree_model import build_localmail_tree, SidebarNode

def test_build_localmail_tree():
    mailboxes = ["a@x.com", "b@y.com"]
    root = build_localmail_tree(mailboxes)
    
    assert isinstance(root, SidebarNode)
    assert root.id == "localmail_root"
    assert root.node_type == "module_root"
    
    # Root has 3 top-level children: "All Mailboxes", "a@x.com", "b@y.com"
    assert len(root.children) == 3
    
    all_node = root.children[0]
    assert all_node.id == "all"
    assert all_node.label == "All Mailboxes"
    assert all_node.node_type == "mailbox"
    assert all_node.mailboxes == mailboxes
    
    # All node has 5 children folder nodes
    assert len(all_node.children) == 5
    folder_types = ["inbox", "sent", "archive", "trash", "drafts"]
    for i, f_type in enumerate(folder_types):
        child = all_node.children[i]
        assert child.id == f"all:{f_type}"
        assert child.node_type == "folder"
        assert child.folder == f_type
        assert child.mailboxes == mailboxes
        
    # Check individual mailboxes
    for idx, m in enumerate(mailboxes):
        m_node = root.children[idx + 1]
        assert m_node.id == m
        assert m_node.label == m
        assert m_node.node_type == "mailbox"
        assert m_node.mailboxes == [m]
        assert len(m_node.children) == 5
        
        for i, f_type in enumerate(folder_types):
            child = m_node.children[i]
            assert child.id == f"{m}:{f_type}"
            assert child.node_type == "folder"
            assert child.folder == f_type
            assert child.mailboxes == [m]
