"""
Bing 壁纸下载器 - 同步版，适合直接集成到 GUI 按钮。

修复点：
- resolution 不再只是文件名，而是参与 Bing 图片 URL 构造。
- 默认 resolution='auto'：检测系统主屏分辨率；检测失败回退 1920x1080。
- 下载失败时自动尝试 1920x1080、UHD、API 原始 URL。
"""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from urllib.parse import urljoin, urlparse

try:
    import httpx
except ImportError:  # pragma: no cover - httpx 为可选依赖，缺失时降级
    httpx = None

try:
    from display_resolution import DEFAULT_RESOLUTION, choose_resolution
except ImportError:
    from .display_resolution import DEFAULT_RESOLUTION, choose_resolution


# 单次同步最大张数限制，防止用户设置过大导致请求过多
MAX_SYNC_COUNT = 16
MAX_IMAGE_BYTES = 64 * 1024 * 1024


@dataclass
class WallpaperInfo:
    id: str
    title: str
    url: str
    copyright: str
    date: str
    resolution: str = DEFAULT_RESOLUTION
    urlbase: str = ""
    resolution_source: str = ""


class BingDownloader:
    API_URLS = [
        "https://www.bing.com/HPImageArchive.aspx",
        "https://cn.bing.com/HPImageArchive.aspx",
    ]
    IMAGE_BASES = ["https://www.bing.com", "https://cn.bing.com"]
    HEADERS = {
        "User-Agent": "ShangBackground/1.1",
        "Accept": "application/json,text/javascript,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://cn.bing.com/",
    }

    def __init__(self, cache_dir: str | None = None, fallback_resolution: str = DEFAULT_RESOLUTION):
        if cache_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            cache_dir = os.path.join(base_dir, "bing_wallpapers")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.fallback_resolution = fallback_resolution
        self._http_client = None

    def _get_http_client(self):
        """获取或创建复用的 httpx 客户端（连接池复用，减少 TCP 握手开销）。"""
        if self._http_client is None and httpx is not None:
            self._http_client = httpx.Client(
                headers=self.HEADERS, timeout=20, follow_redirects=True,
                limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            )
        return self._http_client

    def close(self):
        """关闭 HTTP 客户端，释放连接池资源。"""
        if self._http_client is not None:
            try:
                self._http_client.close()
            except Exception:
                pass
            self._http_client = None

    def _fetch_metadata(self, index: int, mkt: str) -> Optional[dict]:
        if httpx is None:
            print("httpx 未安装，无法获取 Bing 壁纸信息")
            return None
        params = {"format": "js", "idx": index, "n": 1, "mkt": mkt}
        last_error: Exception | None = None
        client = self._get_http_client()
        for api in self.API_URLS:
            try:
                response = client.get(api, params=params)
                response.raise_for_status()
                data = response.json()
                images = data.get("images") or []
                if images:
                    return images[0]
            except Exception as exc:
                last_error = exc
        print(f"获取壁纸信息失败: {last_error}")
        return None

    @staticmethod
    def _is_allowed_bing_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        host = (parsed.hostname or "").lower()
        return parsed.scheme == "https" and (host == "bing.com" or host.endswith(".bing.com"))

    def _url_candidates(self, img: dict, resolution: str) -> list[str]:
        urlbase = img.get("urlbase") or ""
        raw = img.get("url") or ""
        candidates: list[str] = []
        if urlbase:
            for base in self.IMAGE_BASES:
                candidates.append(urljoin(base, f"{urlbase}_{resolution}.jpg"))
                if resolution != self.fallback_resolution:
                    candidates.append(urljoin(base, f"{urlbase}_{self.fallback_resolution}.jpg"))
                candidates.append(urljoin(base, f"{urlbase}_UHD.jpg"))
        if raw:
            for base in self.IMAGE_BASES:
                candidates.append(urljoin(base, raw))
        seen: set[str] = set()
        result: list[str] = []
        for url in candidates:
            if url and url not in seen and self._is_allowed_bing_url(url):
                seen.add(url)
                result.append(url)
        return result

    def fetch_wallpaper_info(self, index: int = 0, mkt: str = "zh-CN", resolution: str | None = "auto") -> Optional[WallpaperInfo]:
        res = choose_resolution(resolution, fallback=self.fallback_resolution)
        img = self._fetch_metadata(index, mkt)
        if not img:
            return None
        img_id = img.get("hsh", hashlib.md5(str(img.get("url", "")).encode()).hexdigest()[:16])
        candidates = self._url_candidates(img, res.resolution)
        return WallpaperInfo(
            id=str(img_id),
            title=img.get("title", "") or img.get("copyright", "Bing Wallpaper"),
            url=candidates[0] if candidates else "",
            copyright=img.get("copyright", ""),
            date=img.get("startdate", datetime.now().strftime("%Y%m%d")),
            resolution=res.resolution,
            urlbase=img.get("urlbase", ""),
            resolution_source=res.source,
        )

    def _safe_filename_part(self, value: str) -> str:
        value = str(value or "").strip()
        return re.sub(r"[^0-9A-Za-z_.-]+", "_", value)[:80] or "unknown"

    def _existing_cached_file(self, info: WallpaperInfo) -> Optional[Path]:
        """按 Bing 图片哈希查找已缓存文件，避免不同日期的重复壁纸重复下载。"""
        if not self.cache_dir.exists():
            return None
        safe_id = self._safe_filename_part(info.id)
        safe_res = self._safe_filename_part(info.resolution)
        patterns = [
            f"bing_*_{safe_id}_{safe_res}.jpg",
            f"bing_{self._safe_filename_part(info.date)}_{safe_res}.jpg",  # 兼容旧版文件名
        ]
        for pattern in patterns:
            for candidate in sorted(self.cache_dir.glob(pattern), reverse=True):
                try:
                    if candidate.is_file() and candidate.stat().st_size > 1024:
                        return candidate
                except OSError:
                    continue
        return None

    def download_wallpaper(self, info: WallpaperInfo, resolution: str | None = None) -> Optional[str]:
        if resolution and resolution not in {info.resolution, "auto", "system", "detect", "native"}:
            # 允许调用方覆盖 info 的分辨率。
            updated = self.fetch_wallpaper_info(0, resolution=resolution)
            if updated:
                info = updated
        existing = self._existing_cached_file(info)
        if existing is not None:
            return str(existing)

        filename = f"bing_{self._safe_filename_part(info.date)}_{self._safe_filename_part(info.id)}_{self._safe_filename_part(info.resolution)}.jpg"
        filepath = self.cache_dir / filename
        if filepath.exists() and filepath.stat().st_size > 1024:
            return str(filepath)

        if httpx is None:
            print("httpx 未安装，无法下载 Bing 壁纸")
            return None
        img_stub = {"urlbase": info.urlbase, "url": info.url}
        urls = self._url_candidates(img_stub, info.resolution) or [info.url]
        last_error: Exception | None = None
        client = self._get_http_client()
        for url in urls:
            try:
                if not self._is_allowed_bing_url(url):
                    raise ValueError("拒绝非 Bing HTTPS 图片地址")
                temp_path = filepath.with_suffix(filepath.suffix + ".part")
                total = 0
                first_chunk = b""
                try:
                    with client.stream("GET", url, timeout=30) as response:
                        response.raise_for_status()
                        ctype = response.headers.get("content-type", "")
                        content_length = response.headers.get("content-length")
                        if content_length and int(content_length) > MAX_IMAGE_BYTES:
                            raise ValueError("图片超过 64MB 限制")
                        with temp_path.open("wb") as output:
                            for chunk in response.iter_bytes(64 * 1024):
                                if not chunk:
                                    continue
                                if not first_chunk:
                                    first_chunk = chunk[:16]
                                total += len(chunk)
                                if total > MAX_IMAGE_BYTES:
                                    raise ValueError("图片超过 64MB 限制")
                                output.write(chunk)
                    if total <= 1024:
                        raise ValueError("图片内容过小或为空")
                    if "image" not in ctype.lower() and not first_chunk.startswith(b"\xff\xd8"):
                        raise ValueError(f"响应不是图片: {ctype}")
                    os.replace(temp_path, filepath)
                finally:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                info.url = url
                print(f"壁纸已下载: {filepath}")
                return str(filepath)
            except Exception as exc:
                last_error = exc
        print(f"下载壁纸失败: {last_error}")
        return None

    def fetch_and_download(self, index: int = 0, mkt: str = "zh-CN", resolution: str | None = "auto") -> Optional[str]:
        info = self.fetch_wallpaper_info(index, mkt, resolution)
        if info:
            return self.download_wallpaper(info)
        return None

    def fetch_history(self, days: int = 7, mkt: str = "zh-CN", resolution: str | None = "auto", start_index: int = 0) -> List[WallpaperInfo]:
        wallpapers: list[WallpaperInfo] = []
        start_index = max(0, int(start_index or 0))
        days = max(0, min(MAX_SYNC_COUNT, int(days or 0)))
        if days <= 0:
            return wallpapers
        # Bing API 单次最多返回 8 张（n 参数上限），所以按 8 张批量请求
        # idx 表示从第几张开始（0=今天，7=最早），最多到 idx≈466 左右有存档
        idx = start_index
        while len(wallpapers) < days:
            # 本轮计划取几张（0~7 的范围，最少取 1）
            remaining = days - len(wallpapers)
            batch_size = min(8, max(1, remaining))
            params = {"format": "js", "idx": idx, "n": batch_size, "mkt": mkt}
            last_error: Exception | None = None
            batch_found = False
            for api in self.API_URLS:
                try:
                    client = self._get_http_client()
                    response = client.get(api, params=params)
                    response.raise_for_status()
                    data = response.json()
                    images = data.get("images") or []
                    if images:
                        batch_found = True
                        for img in images:
                            if len(wallpapers) >= days:
                                break
                            res = choose_resolution(resolution, fallback=self.fallback_resolution)
                            img_id = img.get("hsh", hashlib.md5(str(img.get("url", "")).encode()).hexdigest()[:16])
                            candidates = self._url_candidates(img, res.resolution)
                            info = WallpaperInfo(
                                id=str(img_id),
                                title=img.get("title", "") or img.get("copyright", "Bing Wallpaper"),
                                url=candidates[0] if candidates else "",
                                copyright=img.get("copyright", ""),
                                date=img.get("startdate", ""),
                                resolution=res.resolution,
                                urlbase=img.get("urlbase", ""),
                                resolution_source=res.source,
                            )
                            wallpapers.append(info)
                        break
                except Exception as exc:
                    last_error = exc
            if not batch_found:
                break
            # 本轮没取满说明到头了，或者 idx 已经很大
            if len(images) < batch_size:
                break
            idx += batch_size
        return wallpapers

    def prefetch_wallpapers(self, count: int = 7, mkt: str = "zh-CN", resolution: str | None = "auto") -> List[str]:
        paths: list[str] = []
        for wp in self.fetch_history(count, mkt, resolution):
            path = self.download_wallpaper(wp)
            if path:
                paths.append(path)
        return paths

    def is_bing_cache_file(self, path: Path) -> bool:
        """Only treat files containing 'bing' in the name as managed Bing cache files."""
        try:
            return path.is_file() and path.suffix.lower() in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'} and 'bing' in path.name.lower()
        except OSError:
            return False

    def get_cached_wallpapers(self) -> List[str]:
        if not self.cache_dir.exists():
            return []
        files = [f for f in self.cache_dir.iterdir() if self.is_bing_cache_file(f)]
        files.sort(key=lambda p: (p.stat().st_mtime if p.exists() else 0, p.name.lower()), reverse=True)
        return [str(f) for f in files]


    def delete_oldest_cached_wallpapers(self, count: int, keyword: str = "bing") -> int:
        """Delete a fixed number of oldest cached Bing images, safely limited by filename keyword."""
        count = max(0, int(count or 0))
        if count <= 0:
            return 0
        directory = Path(self.cache_dir)
        if not directory.exists():
            return 0
        candidates: list[Path] = []
        keyword_lower = (keyword or "").lower()
        for item in directory.iterdir():
            if not item.is_file():
                continue
            if item.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
                continue
            if keyword_lower and keyword_lower not in item.name.lower():
                continue
            candidates.append(item)
        candidates.sort(key=lambda p: (p.stat().st_mtime, p.name))
        deleted = 0
        for item in candidates[:count]:
            try:
                item.unlink()
                deleted += 1
            except Exception:
                pass
        return deleted

    def cleanup_cached_wallpapers(self, max_count: int, keyword: str = 'bing') -> int:
        """Delete old managed Bing cache files beyond max_count.

        Safety rule: never delete user images in the same directory unless the filename contains
        the keyword (default: 'bing') and has an image extension.
        """
        max_count = max(0, int(max_count or 0))
        keyword = (keyword or 'bing').lower()
        if not self.cache_dir.exists():
            return 0
        candidates = []
        for path in self.cache_dir.iterdir():
            try:
                if not path.is_file() or path.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}:
                    continue
                if keyword not in path.name.lower():
                    continue
                candidates.append(path)
            except OSError:
                continue
        candidates.sort(key=lambda p: (p.stat().st_mtime if p.exists() else 0, p.name.lower()), reverse=True)
        deleted = 0
        for path in candidates[max_count:]:
            try:
                path.unlink()
                deleted += 1
            except OSError:
                pass
        return deleted

    def get_latest_cached(self) -> Optional[str]:
        cached = self.get_cached_wallpapers()
        return cached[0] if cached else None


_downloader = None


def get_downloader() -> BingDownloader:
    global _downloader
    if _downloader is None:
        _downloader = BingDownloader()
    return _downloader


if __name__ == "__main__":
    dl = BingDownloader()
    print("正在获取并下载今日 Bing 壁纸...")
    print(dl.fetch_and_download(resolution="auto"))
