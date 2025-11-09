import os
import sys
import importlib
import types
import builtins

import pytest


MODULE_PATH = "tools.preload_models"


@pytest.fixture(autouse=True)
def reload_module():
    # Ensure we reload the module fresh for each test where we monkeypatch sys.argv
    if MODULE_PATH in sys.modules:
        del sys.modules[MODULE_PATH]
    yield
    if MODULE_PATH in sys.modules:
        del sys.modules[MODULE_PATH]


def load_module():
    return importlib.import_module(MODULE_PATH)


def test_parse_pair_valid_invalid():
    m = load_module()
    assert m.parse_pair("en->de") == ("en", "de")
    assert m.parse_pair(" EN -> FR ") == ("en", "fr")

    with pytest.raises(ValueError):
        m.parse_pair("en-de")
    with pytest.raises(ValueError):
        m.parse_pair("en->en")
    with pytest.raises(ValueError):
        m.parse_pair("->de")


def test_opus_mt_repo_helpers():
    m = load_module()
    assert m.opus_mt_repo_pairs("de") == [
        "Helsinki-NLP/opus-mt-en-de",
        "Helsinki-NLP/opus-mt-de-en",
    ]
    assert m.opus_mt_repo_for_pair("en", "fr") == "Helsinki-NLP/opus-mt-en-fr"


def test_pairs_mode_direct_download(monkeypatch, capsys, tmp_path):
    """When direct pair exists, we should call download_repo once for the direct repo."""
    # Arrange: stub download_repo to capture calls
    called = []

    def fake_download(repo, dest):
        called.append((repo, dest))

    # Prepare argv for main()
    dest = tmp_path.as_posix()
    argv = [
        "preload_models.py",
        "--family",
        "opus-mt",
        "--pairs",
        "en->de",
        "--dest",
        dest,
    ]

    monkeypatch.setenv("PYTHONWARNINGS", "ignore")
    monkeypatch.setattr(sys, "argv", argv)

    m = load_module()
    monkeypatch.setattr(m, "download_repo", fake_download)

    # Act
    m.main()

    # Assert
    assert called == [("Helsinki-NLP/opus-mt-en-de", os.path.abspath(dest))]
    out = capsys.readouterr().out
    assert "family=opus-mt" in out
    assert "done" in out


def test_pairs_mode_pivot_on_failure(monkeypatch, capsys, tmp_path):
    """If direct non-English pair fails, we expect pivot via en (two downloads)."""
    called = []

    def fake_download(repo, dest):
        # Simulate failure for direct ja->de only
        if repo == "Helsinki-NLP/opus-mt-ja-de":
            raise RuntimeError("no direct model")
        called.append((repo, dest))

    dest = tmp_path.as_posix()
    argv = [
        "preload_models.py",
        "--family",
        "opus-mt",
        "--pairs",
        "ja->de",
        "--dest",
        dest,
    ]

    monkeypatch.setattr(sys, "argv", argv)
    m = load_module()
    monkeypatch.setattr(m, "download_repo", fake_download)

    m.main()

    # Expect pivot via English
    abspath = os.path.abspath(dest)
    assert (
        ("Helsinki-NLP/opus-mt-ja-en", abspath) in called
        and ("Helsinki-NLP/opus-mt-en-de", abspath) in called
    )
    # And not the failed direct one recorded (we raise before appending)
    assert ("Helsinki-NLP/opus-mt-ja-de", abspath) not in called
    err = capsys.readouterr().err
    # Should log pivot usage
    # Message printed to stdout, but ensure we didn't get a hard error
    assert "failed to preload ja->de (direct and pivot failed)" not in err


def test_langs_mode_downloads_both_dirs(monkeypatch, tmp_path):
    """In --langs mode, we should schedule en<->XX for each lang via the repos list."""
    called = []

    def fake_download(repo, dest):
        called.append((repo, dest))

    dest = tmp_path.as_posix()
    argv = [
        "preload_models.py",
        "--family",
        "opus-mt",
        "--langs",
        "de,fr",
        "--dest",
        dest,
    ]

    monkeypatch.setattr(sys, "argv", argv)
    m = load_module()
    monkeypatch.setattr(m, "download_repo", fake_download)

    m.main()

    abspath = os.path.abspath(dest)
    # Order is not strictly guaranteed after de-duplication, so compare as sets
    expected = {
        ("Helsinki-NLP/opus-mt-en-de", abspath),
        ("Helsinki-NLP/opus-mt-de-en", abspath),
        ("Helsinki-NLP/opus-mt-en-fr", abspath),
        ("Helsinki-NLP/opus-mt-fr-en", abspath),
    }
    assert set(called) == expected


def test_invalid_pair_is_skipped(monkeypatch, capsys, tmp_path):
    called = []

    def fake_download(repo, dest):
        called.append((repo, dest))

    dest = tmp_path.as_posix()
    argv = [
        "preload_models.py",
        "--family",
        "opus-mt",
        "--pairs",
        "invalid",
        "--dest",
        dest,
    ]

    monkeypatch.setattr(sys, "argv", argv)
    m = load_module()
    monkeypatch.setattr(m, "download_repo", fake_download)

    m.main()

    # No downloads for invalid pair
    assert called == []
    err = capsys.readouterr().err
    assert "skip invalid pair" in err


def test_no_args_prints_nothing_to_do(monkeypatch, capsys, tmp_path):
    dest = tmp_path.as_posix()
    argv = [
        "preload_models.py",
        "--family",
        "opus-mt",
        "--dest",
        dest,
    ]
    monkeypatch.setattr(sys, "argv", argv)
    m = load_module()

    m.main()

    captured = capsys.readouterr()
    assert "Nothing to do" in captured.err
