"""
GitHub 服务提供商
"""
from typing import Optional, List
from .base import BaseGitProvider, CommitInfo, ReleaseInfo, RepoInfo


class GitHubProvider(BaseGitProvider):
    """GitHub 服务提供商"""

    DEFAULT_API_URL = "https://api.github.com/repos"

    def __init__(self, token: str = "", api_url: str = "", **kwargs):
        super().__init__(token, **kwargs)
        self._api_url = api_url or self.DEFAULT_API_URL
        # 提取基础 API URL (用于组织 API)
        if "repos" in self._api_url:
            self._base_api_url = self._api_url.replace("/repos", "")
        else:
            self._base_api_url = self._api_url.rstrip("/")

    @property
    def name(self) -> str:
        return "GitHub"

    @property
    def api_url(self) -> str:
        return self._api_url

    def get_headers(self) -> dict:
        headers = super().get_headers()
        headers["Accept"] = "application/vnd.github+json"
        return headers

    async def get_default_branch(self, repo: str) -> str:
        url = f"{self._api_url}/{repo}"
        data = await self._fetch_json(url)
        if data and "default_branch" in data:
            return data["default_branch"]
        return "main"

    async def get_latest_commit(self, repo: str, branch: str = "") -> Optional[CommitInfo]:
        if not branch:
            branch = await self.get_default_branch(repo)
        
        url = f"{self._api_url}/{repo}/commits/{branch}"
        data = await self._fetch_json(url)
        
        if not data or "sha" not in data:
            return None
        
        commit = data.get("commit", {})
        author_info = data.get("author", {}) or {}
        
        return CommitInfo(
            sha=data["sha"],
            message=commit.get("message", "").split("\n")[0],
            author=author_info.get("login") or commit.get("author", {}).get("name", "Unknown"),
            date=self._parse_datetime(commit.get("author", {}).get("date", "")),
            branch=branch,
            repo=repo,
            provider=self.name,
            url=f"https://github.com/{repo}/commit/{data['sha']}"
        )

    async def get_latest_release(self, repo: str) -> Optional[ReleaseInfo]:
        url = f"{self._api_url}/{repo}/releases/latest"
        data = await self._fetch_json(url)
        
        if not data or "tag_name" not in data:
            return None
        
        author_info = data.get("author", {}) or {}
        body = data.get("body", "")
        if body:
            body = body.split("\n")[0][:200]
        
        return ReleaseInfo(
            tag=data.get("tag_name", ""),
            name=data.get("name", ""),
            body=body or "无更新说明",
            author=author_info.get("login", "Unknown"),
            date=self._parse_datetime(data.get("published_at", "")),
            repo=repo,
            provider=self.name,
            url=data.get("html_url", f"https://github.com/{repo}/releases/tag/{data.get('tag_name', '')}")
        )

    async def get_group_repos(self, group: str) -> List[RepoInfo]:
        """
        获取 GitHub 组织/用户下的所有仓库
        
        Args:
            group: 组织名或用户名
        
        Returns:
            仓库列表
        """
        repos = []
        
        # 先尝试作为组织获取
        org_url = f"{self._base_api_url}/orgs/{group}/repos"
        org_repos = await self._fetch_all_pages(org_url)
        
        if org_repos:
            for repo_data in org_repos:
                repos.append(RepoInfo(
                    name=repo_data.get("full_name", ""),
                    repo_name=repo_data.get("name", ""),
                    default_branch=repo_data.get("default_branch", "main"),
                    description=repo_data.get("description", ""),
                    url=repo_data.get("html_url", "")
                ))
            return repos
        
        # 如果组织不存在，尝试作为用户获取
        user_url = f"{self._base_api_url}/users/{group}/repos"
        user_repos = await self._fetch_all_pages(user_url)
        
        if user_repos:
            for repo_data in user_repos:
                repos.append(RepoInfo(
                    name=repo_data.get("full_name", ""),
                    repo_name=repo_data.get("name", ""),
                    default_branch=repo_data.get("default_branch", "main"),
                    description=repo_data.get("description", ""),
                    url=repo_data.get("html_url", "")
                ))
        
        return repos
