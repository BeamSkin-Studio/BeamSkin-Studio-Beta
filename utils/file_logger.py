import sys
import io
import os
from datetime import datetime

try:
    from core.settings import get_log_path
except ImportError as _exc:
    print(f"[DEBUG] _pipe_tmp.py: import failed ({_exc}), using fallback")
    def get_log_path():
        return 'data/app_log.txt'


def _log_file_path() -> str:
    return get_log_path()

_file_logging_enabled = False
_log_fp = None


class FileLogOutput(io.StringIO):
    def __init__(self):
        super().__init__()
        self._previous_stdout = sys.stdout
        self._at_line_start = True

    def write(self, message: str) -> int:
        if self._previous_stdout is not None:
            try:
                self._previous_stdout.write(message)
            except Exception as _exc:
                print(f"[WARNING] write: {type(_exc).__name__}: {_exc}")

        if _file_logging_enabled and _log_fp is not None:
            try:
                self._write_to_file(message)
            except Exception as _exc:
                print(f"[WARNING] write: {type(_exc).__name__}: {_exc}")

        return len(message)

    def _write_to_file(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        parts = message.split("\n")
        for i, part in enumerate(parts):
            if part:
                if self._at_line_start:
                    _log_fp.write(f"[{timestamp}] {part}")
                else:
                    _log_fp.write(part)
                self._at_line_start = False
            if i < len(parts) - 1:
                _log_fp.write("\n")
                self._at_line_start = True

        _log_fp.flush()

    def flush(self):
        if self._previous_stdout and hasattr(self._previous_stdout, "flush"):
            try:
                self._previous_stdout.flush()
            except Exception as _exc:
                print(f"[WARNING] flush: {type(_exc).__name__}: {_exc}")
        if _log_fp is not None:
            try:
                _log_fp.flush()
            except Exception as _exc:
                print(f"[WARNING] flush: {type(_exc).__name__}: {_exc}")


def start_file_logging(append: bool) -> bool:
    global _file_logging_enabled, _log_fp

    if _file_logging_enabled and _log_fp is not None:
        return True

    try:
        log_file = _log_file_path()
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        mode = "a" if append else "w"
        _log_fp = open(log_file, mode, encoding="utf-8")

        session_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _log_fp.write(f"\n===== Session started {session_stamp} "
                      f"(mode: {'append' if append else 'overwrite'}) =====\n")
        _log_fp.flush()

        _file_logging_enabled = True

        if not isinstance(sys.stdout, FileLogOutput):
            sys.stdout = FileLogOutput()

        print(f"[DEBUG] File logging started -> {os.path.abspath(log_file)} "
              f"(append={append})")
        return True
    except Exception as e:
        print(f"[WARNING] start_file_logging: {type(e).__name__}: {e}")
        if sys.__stdout__:
            sys.__stdout__.write(f'[ERROR] Could not start file logging: {e}\n')
        _file_logging_enabled = False
        _log_fp = None
        return False


def stop_file_logging() -> None:
    global _file_logging_enabled, _log_fp

    if not _file_logging_enabled:
        return

    print("[DEBUG] File logging stopped")

    _file_logging_enabled = False

    if isinstance(sys.stdout, FileLogOutput):
        sys.stdout = sys.stdout._previous_stdout

    if _log_fp is not None:
        try:
            _log_fp.flush()
            _log_fp.close()
        except Exception as _exc:
            print(f"[WARNING] stop_file_logging: {type(_exc).__name__}: {_exc}")
        _log_fp = None


def is_file_logging_active() -> bool:
    return _file_logging_enabled


def relocate_log_file() -> bool:
    global _log_fp

    if not _file_logging_enabled:
        return True

    try:
        if _log_fp is not None:
            _log_fp.flush()
            _log_fp.close()

        log_file = _log_file_path()
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        _log_fp = open(log_file, "a", encoding="utf-8")

        session_stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _log_fp.write(f"\n===== Log relocated {session_stamp} -> {os.path.abspath(log_file)} =====\n")
        _log_fp.flush()

        print(f"[DEBUG] File logging relocated -> {os.path.abspath(log_file)}")
        return True
    except Exception as e:
        print(f"[WARNING] relocate_log_file: {type(e).__name__}: {e}")
        if sys.__stdout__:
            sys.__stdout__.write(f'[ERROR] Could not relocate log file: {e}\n')
        return False
