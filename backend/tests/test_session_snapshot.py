import pytest
import os
import time
import json
from backend.memory.session_snapshot import load_snapshot, write_snapshot, SessionSnapshot

@pytest.fixture
def temp_snapshot_file(tmp_path):
    return str(tmp_path / "session_snapshot.json")

def test_load_and_write_success(temp_snapshot_file):
    snapshot: SessionSnapshot = {
        "last_topic": "pytest fixtures",
        "open_problems": ["need to test performance"],
        "suggested_next_step": "write the performance test",
        "last_session_timestamp": "2026-07-11T14:30:00Z"
    }
    write_snapshot(temp_snapshot_file, snapshot)
    
    loaded = load_snapshot(temp_snapshot_file)
    assert loaded == snapshot

import logging

def test_missing_file_fails_open(temp_snapshot_file, caplog):
    caplog.set_level(logging.INFO)
    if os.path.exists(temp_snapshot_file):
        os.remove(temp_snapshot_file)
        
    result = load_snapshot(temp_snapshot_file)
    assert result is None
    assert "not found" in caplog.text

def test_corrupted_file_fails_open(temp_snapshot_file, caplog):
    with open(temp_snapshot_file, 'w') as f:
        f.write("{ invalid json")
        
    result = load_snapshot(temp_snapshot_file)
    assert result is None
    assert "corrupted" in caplog.text

def test_missing_keys_fails_open(temp_snapshot_file, caplog):
    with open(temp_snapshot_file, 'w') as f:
        json.dump({"last_topic": "foo"}, f) 
        
    result = load_snapshot(temp_snapshot_file)
    assert result is None
    assert "missing required keys" in caplog.text

def test_load_under_5ms(temp_snapshot_file):
    snapshot: SessionSnapshot = {
        "last_topic": "pytest fixtures",
        "open_problems": ["need to test performance"],
        "suggested_next_step": "write the performance test",
        "last_session_timestamp": "2026-07-11T14:30:00Z"
    }
    write_snapshot(temp_snapshot_file, snapshot)
    
    # Warm up disk/cache
    _ = load_snapshot(temp_snapshot_file)
    
    start = time.perf_counter()
    _ = load_snapshot(temp_snapshot_file)
    duration_ms = (time.perf_counter() - start) * 1000
    
    assert duration_ms < 5.0, f"Load took {duration_ms:.2f}ms, which exceeds 5ms budget"
