from __future__ import annotations

import getpass
import importlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from ima_runtime.shared.config import BOOTSTRAP_STATE_PATH

BOOTSTRAP_KEYRING_SERVICE = "ima-api"
BOOTSTRAP_KEYRING_USERNAME = "default"


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _requirements_path() -> Path:
    return _project_root() / "requirements.txt"


def is_interactive_bootstrap_session(stdin=None, stderr=None) -> bool:
    stdin = stdin or sys.stdin
    stderr = stderr or sys.stderr
    return bool(getattr(stdin, "isatty", lambda: False)() and getattr(stderr, "isatty", lambda: False)())


def _load_keyring_module():
    try:
        return importlib.import_module("keyring")
    except ImportError:
        return None


def _read_state_payload(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_state_payload(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _store_api_key_in_keyring(api_key: str) -> None:
    keyring = _load_keyring_module()
    if keyring is None:
        raise RuntimeError("缺少 `keyring` 依赖，无法安全保存到系统钥匙串。")
    try:
        keyring.set_password(BOOTSTRAP_KEYRING_SERVICE, BOOTSTRAP_KEYRING_USERNAME, api_key.strip())
    except Exception as exc:  # pragma: no cover - backend-dependent
        raise RuntimeError(f"系统钥匙串不可用：{exc}") from exc


def _load_api_key_from_keyring() -> str | None:
    keyring = _load_keyring_module()
    if keyring is None:
        return None
    try:
        api_key = keyring.get_password(BOOTSTRAP_KEYRING_SERVICE, BOOTSTRAP_KEYRING_USERNAME)
    except Exception:  # pragma: no cover - backend-dependent
        return None
    if not isinstance(api_key, str) or not api_key.strip():
        return None
    return api_key.strip()


def load_bootstrap_api_key(state_path: str | Path = BOOTSTRAP_STATE_PATH) -> str | None:
    path = Path(state_path).expanduser()
    payload = _read_state_payload(path)

    legacy_api_key = payload.get("api_key")
    if isinstance(legacy_api_key, str) and legacy_api_key.strip():
        api_key = legacy_api_key.strip()
        try:
            _store_api_key_in_keyring(api_key)
        except RuntimeError:
            return api_key
        _write_state_payload(
            path,
            {
                "storage": "keyring",
                "service": BOOTSTRAP_KEYRING_SERVICE,
                "username": BOOTSTRAP_KEYRING_USERNAME,
            },
        )
        return api_key

    if payload.get("storage") == "keyring":
        return _load_api_key_from_keyring()

    return None


def save_bootstrap_api_key(api_key: str, state_path: str | Path = BOOTSTRAP_STATE_PATH) -> Path:
    path = Path(state_path).expanduser()
    _store_api_key_in_keyring(api_key)
    payload = {
        "storage": "keyring",
        "service": BOOTSTRAP_KEYRING_SERVICE,
        "username": BOOTSTRAP_KEYRING_USERNAME,
    }
    _write_state_payload(path, payload)
    return path


def ensure_runtime_dependency(
    module_name: str = "requests",
    *,
    python_executable: str = sys.executable,
    requirements_path: str | Path | None = None,
    status_stream=None,
) -> bool:
    status_stream = status_stream or sys.stderr
    try:
        importlib.import_module(module_name)
        return False
    except ImportError:
        req_path = Path(requirements_path or _requirements_path()).expanduser()
        print(
            f"📦 Missing dependency '{module_name}'. Installing from {req_path} ...",
            file=status_stream,
        )
        subprocess.run(
            [python_executable, "-m", "pip", "install", "-r", str(req_path)],
            check=True,
        )
        importlib.import_module(module_name)
        print(f"✅ Installed dependency '{module_name}'.", file=status_stream)
        return True


def prompt_for_api_key(status_stream=None, input_stream=None) -> str | None:
    del input_stream
    status_stream = status_stream or sys.stderr
    print("🔐 Enter your IMA_API_KEY to finish bootstrap.", file=status_stream)
    print("   You can get one from https://www.imaclaw.ai/imaclaw/apikey", file=status_stream)
    print("   The key will be stored in your system keyring instead of plaintext JSON.", file=status_stream)
    try:
        api_key = getpass.getpass("IMA_API_KEY: ")
    except (EOFError, KeyboardInterrupt):
        print("\nBootstrap cancelled.", file=status_stream)
        return None
    if not api_key or not api_key.strip():
        print("Bootstrap cancelled: no API key provided.", file=status_stream)
        return None
    return api_key.strip()


def bootstrap_api_key_if_needed(
    *,
    status_stream=None,
    state_path: str | Path = BOOTSTRAP_STATE_PATH,
) -> str | None:
    status_stream = status_stream or sys.stderr
    if not is_interactive_bootstrap_session():
        print(
            "ℹ️ Missing IMA_API_KEY. Run `python3 scripts/ima_create.py --bootstrap` to configure it.",
            file=status_stream,
        )
        return None

    print("⚠️ 未检测到 IMA_API_KEY，正在进入引导模式。", file=status_stream)
    api_key = prompt_for_api_key(status_stream=status_stream)
    if not api_key:
        return None

    try:
        ensure_runtime_dependency("keyring", status_stream=status_stream)
    except Exception:
        pass

    try:
        saved_path = save_bootstrap_api_key(api_key, state_path=state_path)
    except RuntimeError as exc:
        print(f"⚠️ 未能安全保存 IMA_API_KEY：{exc}", file=status_stream)
        print(
            "   当前命令会继续执行；如需下次免配置，请设置环境变量 IMA_API_KEY 或重新运行 --bootstrap。",
            file=status_stream,
        )
        return api_key
    print(f"💾 Saved IMA_API_KEY to keyring via {saved_path}.", file=status_stream)
    return api_key


def run_bootstrap(
    *,
    explicit_api_key: str | None = None,
    state_path: str | Path = BOOTSTRAP_STATE_PATH,
    status_stream=None,
    install_dependencies: bool = True,
    configure_api_key: bool = True,
) -> int:
    status_stream = status_stream or sys.stderr
    if install_dependencies:
        try:
            ensure_runtime_dependency(status_stream=status_stream)
            ensure_runtime_dependency("keyring", status_stream=status_stream)
        except Exception as exc:
            print(f"❌ Bootstrap failed while installing dependencies: {exc}", file=status_stream)
            return 1

    if not configure_api_key:
        print("✅ Bootstrap complete: runtime dependencies are ready.", file=status_stream)
        return 0

    api_key = explicit_api_key or os.getenv("IMA_API_KEY") or load_bootstrap_api_key(state_path=state_path)
    if not api_key:
        api_key = prompt_for_api_key(status_stream=status_stream)
        if not api_key:
            return 1

    try:
        saved_path = save_bootstrap_api_key(api_key, state_path=state_path)
    except RuntimeError as exc:
        print(f"❌ Bootstrap could not save IMA_API_KEY securely: {exc}", file=status_stream)
        print("   Use `export IMA_API_KEY=...` for this session, then re-run bootstrap after fixing keyring.", file=status_stream)
        return 1
    print(f"💾 Saved IMA_API_KEY to keyring via {saved_path}.", file=status_stream)
    print("✅ Bootstrap complete: dependencies and API key are ready.", file=status_stream)
    return 0


__all__ = [
    "bootstrap_api_key_if_needed",
    "ensure_runtime_dependency",
    "is_interactive_bootstrap_session",
    "load_bootstrap_api_key",
    "prompt_for_api_key",
    "run_bootstrap",
    "save_bootstrap_api_key",
]
