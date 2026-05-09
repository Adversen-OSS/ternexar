import pytest
from pathlib import Path
from ternexar.workspace import WorkspaceManager

def test_path_safety():
    mgr = WorkspaceManager()
    assert mgr.is_path_safe("/home/teju/projects") is True
    assert mgr.is_path_safe("/etc") is False
    assert mgr.is_path_safe("/") is False
    assert mgr.is_path_safe("/usr/bin") is False

def test_file_safety(tmp_path):
    mgr = WorkspaceManager()
    
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET=123")
    assert mgr.is_file_safe(env_file) is False
    
    key_file = tmp_path / "id_rsa.key"
    key_file.write_text("PRIVATE KEY")
    assert mgr.is_file_safe(key_file) is False
    
    readme = tmp_path / "README.md"
    readme.write_text("Hello World")
    assert mgr.is_file_safe(readme) is True
    
    large_file = tmp_path / "large.txt"
    large_file.write_text("A" * 200000) # > 100 KB
    assert mgr.is_file_safe(large_file) is False

def test_get_tree(tmp_path):
    mgr = WorkspaceManager()
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print(1)")
    (tmp_path / "README.md").write_text("docs")
    (tmp_path / "node_modules").mkdir()
    
    tree = mgr.get_tree(str(tmp_path))
    assert tree["name"] == tmp_path.name
    
    children = [c["name"] for c in tree["children"]]
    assert "src" in children
    assert "README.md" in children
    assert "node_modules" not in children

def test_scan_python(tmp_path):
    mgr = WorkspaceManager()
    (tmp_path / "pyproject.toml").write_text("[project]")
    (tmp_path / "README.md").write_text("# My Project")
    
    report = mgr.scan(str(tmp_path))
    assert report["project_type"] == "PYTHON"
    assert "pyproject.toml" in report["important_files"]
    assert report["readme_preview"].startswith("# My Project")

def test_scan_node(tmp_path):
    mgr = WorkspaceManager()
    (tmp_path / "package.json").write_text("{}")
    
    report = mgr.scan(str(tmp_path))
    assert report["project_type"] == "NODE"
