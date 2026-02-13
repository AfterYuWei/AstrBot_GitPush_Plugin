"""
CNB (cnb.cool) 服务提供商
"""
from typing import Optional, List
from .base import BaseGitProvider, CommitInfo, ReleaseInfo, RepoInfo


class CNBProvider(BaseGitProvider):
    """CNB 服务提供商"""

    DEFAULT_API_URL = "https://api.cnb.cool"

    def __init__(self, token: str = "", api_url: str = "", **kwargs):
        super().__init__(token, **kwargs)
        self._api_url = api_url or self.DEFAULT_API_URL

    @property
    def name(self) -> str:
        return "CNB"

    @property
    def api_url(self) -> str:
        return self._api_url

    async def get_default_branch(self, repo: str) -> str:
        url = f"{self._api_url}/{repo}/-/git/head"
        data = await self._fetch_json(url)
        if data and "name" in data:
            return data["name"]
        return "main"

    async def get_latest_commit(self, repo: str, branch: str = "") -> Optional[CommitInfo]:
        if not branch:
            branch = await self.get_default_branch(repo)
        
        # CNB 的 commits API
        if branch:
            url = f"{self._api_url}/{repo}/-/git/commits/{branch}"
        else:
            url = f"{self._api_url}/{repo}/-/git/commits"
        
        data = await self._fetch_json(url)
        
        if not data:
            return None
        
        # 如果返回的是列表，取第一个
        if isinstance(data, list):
            if len(data) == 0:
                return None
            commit = data[0]
        else:
            commit = data
        
        sha = commit.get("sha", commit.get("id", ""))
        
        return CommitInfo(
            sha=sha,
            message=commit.get("message", "").split("\n")[0],
            author=commit.get("author", {}).get("name", commit.get("author_name", "Unknown")),
            date=self._parse_datetime(commit.get("committed_date", commit.get("created_at", ""))),
            branch=branch,
            repo=repo,
            provider=self.name,
            url=f"https://cnb.cool/{repo}/-/commit/{sha}"
        )

    async def get_latest_release(self, repo: str) -> Optional[ReleaseInfo]:
        url = f"{self._api_url}/{repo}/-/releases"
        data = await self._fetch_json(url)
        
        if not data:
            return None
        
        # 如果返回的是列表，取第一个
        if isinstance(data, list):
            if len(data) == 0:
                return None
            release = data[0]
        else:
            release = data
        
        tag = release.get("tag_name", release.get("tag", ""))
        body = release.get("body", release.get("description", ""))
        if body:
            body = body.split("\n")[0][:200]
        
        author_info = release.get("author", {}) or {}
        
        return ReleaseInfo(
            tag=tag,
            name=release.get("name", tag),
            body=body or "无更新说明",
            author=author_info.get("username", author_info.get("login", "Unknown")),
            date=self._parse_datetime(release.get("published_at", release.get("released_at", ""))),
            repo=repo,
            provider=self.name,
            url=f"https://cnb.cool/{repo}/-/releases/{tag}"
        )

    async def get_group_repos(self, group: str) -> List[RepoInfo]:
        """
        获取 CNB 群组下的所有仓库
        
        Args:
            group: 群组名
        
        Returns:
            仓库列表
        """
        repos = []
        
        # CNB 群组仓库 API
        url = f"{self._api_url}/{group}/-/repos"
        data = await self._fetch_all_pages(url)
        
        if data:
            for repo_data in data:
                repo_name = repo_data.get("name", repo_data.get("path", ""))
                full_name = f"{group}/{repo_name}"
                
                repos.append(RepoInfo(
                    name=full_name,
                    repo_name=repo_name,
                    default_branch=repo_data.get("default_branch", "main"),
                    description=repo_data.get("description", ""),
                    url=f"https://cnb.cool/{full_name}"
                ))
        
        return repos
