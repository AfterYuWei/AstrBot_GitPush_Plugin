"""
数据存储模块
"""
import os
import json
from typing import Dict, Any, Optional, Set


class DataStorage:
    """数据存储"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.cache_file = os.path.join(data_dir, "cache.json")
        self._ensure_dir()

    def _ensure_dir(self):
        """确保目录存在"""
        os.makedirs(self.data_dir, exist_ok=True)

    def load_cache(self) -> Dict[str, Any]:
        """加载缓存数据"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_cache(self, cache: Dict[str, Any]):
        """保存缓存数据"""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


class UpdateCache:
    """更新缓存管理"""

    def __init__(self, storage: DataStorage):
        self.storage = storage
        self._cache: Dict[str, Dict] = {}
        self._repo_cache: Dict[str, Set[str]] = {}  # 群组下的仓库缓存
        self._load()

    def _load(self):
        """加载缓存"""
        self._cache = self.storage.load_cache()
        # 加载群组仓库映射
        if "_group_repos" in self._cache:
            for group_key, repos in self._cache["_group_repos"].items():
                self._repo_cache[group_key] = set(repos)

    def _save(self):
        """保存缓存"""
        # 保存群组仓库映射
        self._cache["_group_repos"] = {
            k: list(v) for k, v in self._repo_cache.items()
        }
        self.storage.save_cache(self._cache)

    def _get_commit_key(self, provider: str, repo: str, branch: str) -> str:
        """生成提交缓存键"""
        return f"commit:{provider}:{repo}:{branch}"

    def _get_release_key(self, provider: str, repo: str) -> str:
        """生成发布缓存键"""
        return f"release:{provider}:{repo}"

    # ============ 提交缓存 ============

    def get_cached_commit_sha(self, provider: str, repo: str, branch: str) -> Optional[str]:
        """获取缓存的提交 SHA"""
        key = self._get_commit_key(provider, repo, branch)
        return self._cache.get(key, {}).get("sha")

    def set_cached_commit_sha(self, provider: str, repo: str, branch: str, sha: str):
        """设置缓存的提交 SHA"""
        key = self._get_commit_key(provider, repo, branch)
        if key not in self._cache:
            self._cache[key] = {}
        self._cache[key]["sha"] = sha
        self._save()

    def is_first_commit_check(self, provider: str, repo: str, branch: str) -> bool:
        """检查是否是首次检查提交"""
        key = self._get_commit_key(provider, repo, branch)
        return key not in self._cache

    # ============ 发布缓存 ============

    def get_cached_release_tag(self, provider: str, repo: str) -> Optional[str]:
        """获取缓存的发布标签"""
        key = self._get_release_key(provider, repo)
        return self._cache.get(key, {}).get("tag")

    def set_cached_release_tag(self, provider: str, repo: str, tag: str):
        """设置缓存的发布标签"""
        key = self._get_release_key(provider, repo)
        if key not in self._cache:
            self._cache[key] = {}
        self._cache[key]["tag"] = tag
        self._save()

    def is_first_release_check(self, provider: str, repo: str) -> bool:
        """检查是否是首次检查发布"""
        key = self._get_release_key(provider, repo)
        return key not in self._cache

    # ============ 群组仓库缓存 ============

    def _get_group_key(self, provider: str, group: str) -> str:
        """生成群组缓存键"""
        return f"{provider}:{group}"

    def get_group_cached_repos(self, provider: str, group: str) -> Set[str]:
        """获取群组已缓存的仓库列表"""
        key = self._get_group_key(provider, group)
        return self._repo_cache.get(key, set())

    def set_group_cached_repos(self, provider: str, group: str, repos: Set[str]):
        """设置群组已缓存的仓库列表"""
        key = self._get_group_key(provider, group)
        self._repo_cache[key] = repos
        self._save()

    def add_repo_to_group_cache(self, provider: str, group: str, repo: str):
        """向群组缓存添加仓库"""
        key = self._get_group_key(provider, group)
        if key not in self._repo_cache:
            self._repo_cache[key] = set()
        self._repo_cache[key].add(repo)
        self._save()

    # ============ 通用方法 ============

    def is_first_time(self, provider: str, repo: str, branch: str, watch_type: str) -> bool:
        """检查是否是首次检查（向后兼容）"""
        if watch_type == "commits":
            return self.is_first_commit_check(provider, repo, branch)
        else:
            return self.is_first_release_check(provider, repo)

    def clear_cache(self, provider: str = None, repo: str = None):
        """清除缓存"""
        if provider and repo:
            # 清除特定仓库的缓存
            keys_to_remove = [k for k in self._cache 
                            if not k.startswith("_") and f"{provider}:{repo}" in k]
            for key in keys_to_remove:
                del self._cache[key]
        elif provider:
            # 清除特定提供商的缓存
            keys_to_remove = [k for k in self._cache 
                            if not k.startswith("_") and k.endswith(f":{provider}") or f":{provider}:" in k]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            # 清除所有缓存（保留元数据）
            self._cache = {k: v for k, v in self._cache.items() if k.startswith("_")}
            self._repo_cache = {}
        self._save()

    def clear_group_cache(self, provider: str = None, group: str = None):
        """清除群组缓存"""
        if provider and group:
            key = self._get_group_key(provider, group)
            if key in self._repo_cache:
                del self._repo_cache[key]
        elif provider:
            keys_to_remove = [k for k in self._repo_cache if k.startswith(f"{provider}:")]
            for key in keys_to_remove:
                del self._repo_cache[key]
        else:
            self._repo_cache = {}
        self._save()
