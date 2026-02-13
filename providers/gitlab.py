"""
GitLab 服务提供商
支持自部署的 GitLab 实例
"""
import urllib.parse
from typing import Optional, List
from .base import BaseGitProvider, CommitInfo, ReleaseInfo, RepoInfo


class GitLabProvider(BaseGitProvider):
    """GitLab 服务提供商"""

    DEFAULT_API_URL = "https://gitlab.com/api/v4"

    def __init__(self, token: str = "", api_url: str = "", **kwargs):
        super().__init__(token, **kwargs)
        self._api_url = api_url or self.DEFAULT_API_URL
        # 提取基础 URL 用于构建链接
        self._base_url = self._api_url.replace("/api/v4", "").rstrip("/")

    @property
    def name(self) -> str:
        return "GitLab"

    @property
    def api_url(self) -> str:
        return self._api_url

    def _encode_project(self, repo: str) -> str:
        """URL 编码项目路径"""
        return urllib.parse.quote(repo, safe='')

    def get_headers(self) -> dict:
        headers = super().get_headers()
        if self.token:
            # GitLab 使用 PRIVATE-TOKEN 或 Authorization
            headers["PRIVATE-TOKEN"] = self.token
        return headers

    async def get_default_branch(self, repo: str) -> str:
        encoded_repo = self._encode_project(repo)
        url = f"{self._api_url}/projects/{encoded_repo}"
        data = await self._fetch_json(url)
        if data and "default_branch" in data:
            return data["default_branch"]
        return "main"

    async def get_latest_commit(self, repo: str, branch: str = "") -> Optional[CommitInfo]:
        if not branch:
            branch = await self.get_default_branch(repo)
        
        encoded_repo = self._encode_project(repo)
        url = f"{self._api_url}/projects/{encoded_repo}/repository/commits"
        params = {"per_page": 1}
        if branch:
            params["ref_name"] = branch
        
        data = await self._fetch_json(url, params)
        
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        
        commit = data[0]
        
        # 构建提交 URL
        commit_url = f"{self._base_url}/{repo}/-/commit/{commit.get('id', '')}"
        
        return CommitInfo(
            sha=commit.get("id", ""),
            message=commit.get("message", "").split("\n")[0],
            author=commit.get("author_name", "Unknown"),
            date=self._parse_datetime(commit.get("committed_date", "")),
            branch=branch,
            repo=repo,
            provider=self.name,
            url=commit_url
        )

    async def get_latest_release(self, repo: str) -> Optional[ReleaseInfo]:
        encoded_repo = self._encode_project(repo)
        url = f"{self._api_url}/projects/{encoded_repo}/releases"
        
        data = await self._fetch_json(url)
        
        if not data or not isinstance(data, list) or len(data) == 0:
            return None
        
        # 过滤 draft 版本，获取第一个正式版本
        release = None
        for r in data:
            if not r.get("draft", False):
                release = r
                break
        
        if not release:
            release = data[0]
        
        body = release.get("description", "")
        if body:
            body = body.split("\n")[0][:200]
        
        author_info = release.get("author", {}) or {}
        
        # 构建发布 URL
        release_url = release.get("_links", {}).get("self") or \
                      f"{self._base_url}/{repo}/-/releases/{release.get('tag_name', '')}"
        
        return ReleaseInfo(
            tag=release.get("tag_name", ""),
            name=release.get("name", release.get("tag_name", "")),
            body=body or "无更新说明",
            author=author_info.get("username", "Unknown"),
            date=self._parse_datetime(release.get("released_at", "")),
            repo=repo,
            provider=self.name,
            url=release_url
        )

    async def get_group_repos(self, group: str) -> List[RepoInfo]:
        """
        获取 GitLab 群组下的所有项目
        
        Args:
            group: 群组路径 (如: my-group 或 parent-group/sub-group)
        
        Returns:
            仓库列表
        """
        repos = []
        
        # URL 编码群组路径
        encoded_group = urllib.parse.quote(group, safe='')
        
        # GitLab 群组项目 API
        url = f"{self._api_url}/groups/{encoded_group}/projects"
        params = {
            "include_subgroups": "true",  # 包含子群组
            "archived": "false"  # 不包含已归档项目
        }
        
        projects = await self._fetch_all_pages(url, params)
        
        if projects:
            for project in projects:
                repos.append(RepoInfo(
                    name=project.get("path_with_namespace", ""),
                    repo_name=project.get("path", ""),
                    default_branch=project.get("default_branch", "main"),
                    description=project.get("description", ""),
                    url=project.get("web_url", "")
                ))
        
        return repos
