from __future__ import annotations

import json
import logging
import math
import os
import random
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger("ShangBackground.random_copy")
logger.addHandler(logging.NullHandler())

COPY_PREFIX = "(xxdz_random_copy)"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEGACY_RANDOM_CONFIG_PATH = os.path.join(BASE_DIR, "random.json")
RANDOM_CONFIG_PATH = LEGACY_RANDOM_CONFIG_PATH
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".gif")
DEFAULT_WEIGHT = 100.0
MAX_WEIGHT = 1_000_000.0
_CONFIG_LOCK = threading.RLock()


def log(message: str) -> None:
    timestamp = time.strftime("[%H:%M:%S]")
    print(f"{timestamp} {message}")
    logger.info(message)


def configure_storage(data_dir: str) -> str:
    """Store random.json in the per-user writable data directory."""
    global RANDOM_CONFIG_PATH
    target_dir = Path(data_dir).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "random.json"
    legacy_candidates = [Path(LEGACY_RANDOM_CONFIG_PATH)]
    if getattr(sys, "frozen", False):
        legacy_candidates.append(Path(sys.executable).resolve().parent / "random.json")
    if not target.exists():
        for legacy in legacy_candidates:
            if target == legacy or not legacy.is_file():
                continue
            try:
                payload = legacy.read_bytes()
                json.loads(payload.decode("utf-8"))
                temp = target.with_suffix(".json.tmp")
                temp.write_bytes(payload)
                os.replace(temp, target)
                break
            except Exception as exc:
                log(f"迁移旧随机配置失败: {exc}")
    RANDOM_CONFIG_PATH = str(target)
    return RANDOM_CONFIG_PATH


def _load_config() -> dict:
    with _CONFIG_LOCK:
        path = Path(RANDOM_CONFIG_PATH)
        if not path.is_file():
            return {"__version__": 3, "folders": {}}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {"__version__": 3, "folders": {}}
        except Exception as exc:
            log(f"读取随机配置失败: {exc}")
            return {"__version__": 3, "folders": {}}


def _save_config(data: dict) -> None:
    with _CONFIG_LOCK:
        path = Path(RANDOM_CONFIG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        try:
            temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                os.chmod(temp, 0o600)
            except OSError:
                pass
            os.replace(temp, path)
        except Exception:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise


def _folder_key(folder_path: str) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(folder_path)))


def _folder_data(config: dict, folder_abs: str) -> dict:
    if isinstance(config.get("folders"), dict):
        value = config["folders"].get(folder_abs, {})
        return value if isinstance(value, dict) else {}
    value = config.get(folder_abs, {})
    return value if isinstance(value, dict) else {}


def _safe_weight(value, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return min(MAX_WEIGHT, max(0.0, number))


def get_original_image_paths(folder_path: str) -> list[str]:
    folder_abs = os.path.abspath(folder_path)
    if not os.path.isdir(folder_abs):
        return []
    paths: list[str] = []
    try:
        entries = os.scandir(folder_abs)
    except OSError:
        return []
    with entries:
        for entry in entries:
            name = entry.name
            if name.startswith(COPY_PREFIX):
                continue
            try:
                is_file = entry.is_file(follow_symlinks=True)
            except OSError:
                continue
            if is_file and name.lower().endswith(IMAGE_EXTENSIONS):
                paths.append(entry.path)
    return sorted(paths, key=lambda value: os.path.basename(value).casefold())


def get_probability_weights(folder_path: str) -> dict[str, float]:
    folder_abs = _folder_key(folder_path)
    folder_data = _folder_data(_load_config(), folder_abs)
    return {
        str(filename): _safe_weight(value)
        for filename, value in folder_data.items()
        if isinstance(filename, str)
    }


def _migrate_folders(config: dict) -> dict:
    folders = config.get("folders") if isinstance(config, dict) else None
    if not isinstance(folders, dict):
        folders = {}
        if isinstance(config, dict):
            for key, value in config.items():
                if isinstance(value, dict) and os.path.isabs(str(key)):
                    folders[_folder_key(str(key))] = value
    return {"__version__": 3, "folders": folders}


def save_probability_weights(folder_path: str, weights_dict: dict) -> None:
    folder_abs = _folder_key(folder_path)
    if not os.path.isdir(folder_abs):
        raise ValueError("壁纸文件夹无效")

    originals = [os.path.basename(path) for path in get_original_image_paths(folder_abs)]
    if not originals:
        raise ValueError("壁纸文件夹中没有支持的图片")

    config = _migrate_folders(_load_config())
    folders = config["folders"]
    previous = _folder_data(config, folder_abs)
    requested = weights_dict if isinstance(weights_dict, dict) else {}
    cleaned: dict[str, float] = {}
    for filename in originals:
        if filename in requested:
            value = _safe_weight(requested[filename])
        elif filename in previous:
            value = _safe_weight(previous[filename])
        else:
            value = DEFAULT_WEIGHT
        # Keep explicit zeroes: zero means disabled and must not fall back to DEFAULT_WEIGHT.
        cleaned[filename] = round(value, 4)

    if not any(value > 0 for value in cleaned.values()):
        raise ValueError("至少需要一张壁纸的概率大于 0%")
    folders[folder_abs] = cleaned
    _save_config(config)
    cleanup_physical_only(folder_abs)


def weighted_choice(folder_path: str, current_path: str = "") -> str | None:
    originals = get_original_image_paths(folder_path)
    if not originals:
        return None

    weights_map = get_probability_weights(folder_path)
    eligible: list[str] = []
    weights: list[float] = []
    for path in originals:
        filename = os.path.basename(path)
        weight = _safe_weight(weights_map.get(filename, DEFAULT_WEIGHT), DEFAULT_WEIGHT)
        if weight > 0:
            eligible.append(path)
            weights.append(weight)

    if not eligible:
        eligible = list(originals)
        weights = [1.0] * len(eligible)

    current_abs = os.path.realpath(os.path.abspath(current_path)) if current_path else ""
    if current_abs and len(eligible) > 1:
        filtered = [(path, weight) for path, weight in zip(eligible, weights) if os.path.realpath(os.path.abspath(path)) != current_abs]
        if filtered:
            eligible, weights = map(list, zip(*filtered))
    return random.choices(eligible, weights=weights, k=1)[0]


def _delete_copies(folder_abs: str, filename: str | None = None) -> int:
    if not os.path.isdir(folder_abs):
        return 0
    deleted = 0
    try:
        names = os.listdir(folder_abs)
    except OSError:
        return 0
    for name in names:
        if not name.startswith(COPY_PREFIX):
            continue
        if filename is not None and not name.endswith(filename):
            continue
        path = os.path.join(folder_abs, name)
        try:
            if os.path.isfile(path):
                os.remove(path)
                deleted += 1
        except OSError:
            continue
    return deleted


def cleanup_physical_only(folder_path: str) -> int:
    folder_abs = os.path.abspath(folder_path)
    deleted = _delete_copies(folder_abs)
    if deleted:
        log(f"已清理 {deleted} 个旧版概率副本文件")
    return deleted


# Compatibility API: legacy callers keep working, but no longer create physical copies.
def get_copy_count(folder_path: str, filename: str) -> float:
    return get_probability_weights(folder_path).get(filename, 0.0)


def save_all_changes(folder_path: str, changes_dict: dict) -> None:
    save_probability_weights(folder_path, changes_dict)


def cleanup_folder(folder_path: str) -> None:
    folder_abs = _folder_key(folder_path)
    cleanup_physical_only(folder_abs)
    config = _migrate_folders(_load_config())
    config["folders"].pop(folder_abs, None)
    _save_config(config)


def restore_weights(folder_path: str) -> None:
    cleanup_physical_only(folder_path)


def get_all_images_with_copies(folder_path: str) -> list[str]:
    return get_original_image_paths(folder_path)


def open_random_probability_window(parent, folder):
    raise RuntimeError("随机概率图形设置已整合到 PySide6 主界面，请从新版界面调整随机百分比。")
