import logging

from src.app import logging_config


def test_configure_logging_creates_script_and_error_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)

    log_path = logging_config.configure_logging("test_script", console=False, force=True)
    logging.getLogger("test").info("hello")
    logging.getLogger("test").error("boom")

    assert log_path.exists()
    assert (tmp_path / "errors.log").exists()
    assert "hello" in log_path.read_text(encoding="utf-8")
    assert "boom" in (tmp_path / "errors.log").read_text(encoding="utf-8")
