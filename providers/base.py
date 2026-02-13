"""
Git 服务提供商基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime
import aiohttp


@dataclass
class CommitInfo:
    """提交信息"""
    sha: str
    message: str
    author: str
    date: str
    branch: str
    repo: str
    provider: str
    url: Optional[str] = None

    def to_push_message(self) -> str:
        """转换为推送消息"""
        text = f"📦 【{self.provider}】{self.repo}\n"
        text += f"🌿 分支: {self.branch}\n"
        text += f"📝 提交: {self.sha[:7]}\n"
        text += f"👤 作者: {self.author}\n"
        text += f"⏰ 时间: {self.date}\n"
        text += f"💬 信息: {self.message}"
        if self.url:
            text += f"\n🔗 链接: {self.url}"
        return text


@dataclass
class ReleaseInfo:
    """发布信息"""
    tag: str
    name: str
    body: str
    author: str
    date: str
    repo: str
    provider: str
    url: Optional[str] = None

    def to_push_message(self) -> str:
        """转换为推送消息"""
        text = f"🚀 【{self.provider}】{self.repo}\n"
        text += f"🏷️ 版本: {self.tag}\n"
        if self.name and self.name != self.tag:
            text += f"📋 名称: {self.name}\n"
        if self.author:
            text += f"👤 发布者: {self.author}\n"
        text += f"⏰ 时间: {self.date}\n"
        text += f"📄 说明: {self.body[:200]}"
        if self.url:
            text += f"\n🔗 链接: {self.url}"
        return text


@dataclass
class RepoInfo:
    """仓库基本信息"""
    name: str  # 仓库名 (owner/repo 格式)
    repo_name: str  # 仅仓库名
    default_branch: str
    description: str = ""
    url: str = ""


class BaseGitProvider(ABC):
    """Git 服务提供商基类"""

    def __init__(self, token: str = "", **kwargs):
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None
        self.config = kwargs

    @property
    @abstractmethod
    def name(self) -> str:
        """提供商名称"""
        pass

    @property
    @abstractmethod
    def api_url(self) -> str:
        """API 基础地址"""
        pass

    async def init(self):
        """初始化会话"""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """关闭会话"""
        if self.session:
            await self.session.close()
            self.session = None

    def get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        headers = {
            "User-Agent": "AstrBot-GitPush-Plugin",
            "Accept": "application/json"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    @abstractmethod
    async def get_default_branch(self, repo: str) -> str:
        """
        获取默认分支
        
        Args:
            repo: 仓库名 (owner/repo)
        
        Returns:
            默认分支名
        """
        pass

    @abstractmethod
    async def get_latest_commit(self, repo: str, branch: str = "") -> Optional[CommitInfo]:
        """
        获取最新提交
        
        Args:
            repo: 仓库名 (owner/repo)
            branch: 分支名，为空则使用默认分支
        
        Returns:
            提交信息，失败返回 None
        """
        pass

    @abstractmethod
    async def get_latest_release(self, repo: str) -> Optional[ReleaseInfo]:
        """
        获取最新发布
        
        Args:
            repo: 仓库名 (owner/repo)
        
        Returns:
            发布信息，失败返回 None
        """
        pass

    async def get_group_repos(self, group: str) -> List[RepoInfo]:
        """
        获取群组/组织下的所有仓库
        
        Args:
            group: 组织名/群组名
        
        Returns:
            仓库列表
        """
        # 默认实现返回空列表，子类可重写
        return []

    def _parse_datetime(self, date_str: str) -> str:
        """解析日期时间"""
        if not date_str:
            return "未知"
        try:
            # 处理 ISO 格式
            if "T" in date_str:
                date_str = date_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(date_str)
                return dt.strftime("%Y-%m-%d %H:%M")
        except:
            pass
        return date_str

    async def _fetch_json(self, url: str, params: Dict = None) -> Optional[Any]:
        """获取 JSON 数据"""
        if not self.session:
            await self.init()
        
        try:
            async with self.session.get(
                url, 
                headers=self.get_headers(), 
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                elif resp.status == 404:
                    return None
                else:
                    return None
        except Exception:
            return None

    async def _fetch_all_pages(self, url: str, params: Dict = None, max_pages: int = 10) -> List[Dict]:
        """获取所有分页数据"""
        if not self.session:
            await self.init()
        
        all_data = []
        page = 1
        per_page = 100
        
        base_params = params or {}
        
        while page <= max_pages:
            page_params = {**base_params, "page": page, "per_page": per_page}
            
            try:
                async with self.session.get(
                    url,
                    headers=self.get_headers(),
                    params=page_params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        break
                    
                    data = await resp.json()
                    if not data:
                        break
                    
                    if isinstance(data, list):
                        all_data.extend(data)
                        if len(data) < per_page:
                            break
                    else:
                        break
                    
                    page += 1
            except Exception:
                break
        
        return all_data
