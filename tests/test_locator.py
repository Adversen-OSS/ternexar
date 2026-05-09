import pytest
from pathlib import Path
from ternexar.locator import ProjectLocator

def test_locator_search(tmp_path):
    # Setup mock structure
    project_dir = tmp_path / "my-cool-project"
    project_dir.mkdir()
    
    hidden_dir = tmp_path / ".git"
    hidden_dir.mkdir()
    
    skip_dir = tmp_path / "node_modules"
    skip_dir.mkdir()
    
    deep_dir = tmp_path / "a" / "b" / "c" / "d" / "e" / "my-deep-project"
    deep_dir.mkdir(parents=True)
    
    locator = ProjectLocator()
    # Override roots for testing
    locator.roots = [tmp_path]
    
    # Test match
    results = locator.locate("cool")
    assert len(results) == 1
    assert results[0]["name"] == "my-cool-project"
    
    # Test skip hidden
    results = locator.locate(".git")
    assert len(results) == 0
    
    # Test skip folders
    results = locator.locate("node_modules")
    assert len(results) == 0
    
    # Test depth limit (MAX_DEPTH=4)
    # root/a/b/c/d/e/my-deep-project
    # root (0) -> scans a (1)
    # a (1) -> scans b (2)
    # b (2) -> scans c (3)
    # c (3) -> scans d (4)
    # d (4) -> scans e (5)
    # e (5) -> depth 5 > 4. Returns.
    # So 'e' is the last one found. 'my-deep-project' is inside 'e'.
    results = locator.locate("deep")
    assert len(results) == 0
