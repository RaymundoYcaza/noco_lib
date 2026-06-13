import sys
from pathlib import Path

# Add paths to sys.path
root_dir = Path(__file__).resolve().parent.parent
tardis_dir = root_dir / "tardis"
if str(tardis_dir) not in sys.path:
    sys.path.insert(0, str(tardis_dir))

from app_core.sidebar.tree_model import build_localmail_tree

def main():
    print("--- Testing Sidebar Tree Model ---")
    mailboxes = ["a@x.com", "b@y.com"]
    root = build_localmail_tree(mailboxes)
    
    print(f"Root: {root.id} (node_type={root.node_type})")
    
    assert root.id == "localmail_root"
    assert len(root.children) == 3
    print("Passed: Root has 3 top-level children")
    
    # Check "All Mailboxes"
    all_node = root.children[0]
    print(f" - Child 1: {all_node.label} (id={all_node.id})")
    assert all_node.id == "all"
    assert len(all_node.children) == 5
    print("   Passed: All Mailboxes has 5 folders")
    
    # Check "a@x.com"
    a_node = root.children[1]
    print(f" - Child 2: {a_node.label} (id={a_node.id})")
    assert a_node.id == "a@x.com"
    assert len(a_node.children) == 5
    assert a_node.children[1].id == "a@x.com:sent"
    print("   Passed: a@x.com has 5 folders, ID format correct")
    
    # Check "b@y.com"
    b_node = root.children[2]
    print(f" - Child 3: {b_node.label} (id={b_node.id})")
    assert b_node.id == "b@y.com"
    assert len(b_node.children) == 5
    assert b_node.children[3].id == "b@y.com:trash"
    print("   Passed: b@y.com has 5 folders, ID format correct")
    
    print("--- Tree Model Verification Successful ---")

if __name__ == "__main__":
    main()
