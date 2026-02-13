"""
配置管理模块
支持仓库级别和群组级别的监听配置
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json


@dataclass
class RepoWatchConfig:
    """仓库监听配置"""
    provider: str  # github, gitlab, cnb
    repo: str  # owner/repo
    branch: str = ""  # 分支，为空则使用默认分支
    watch_type: str = "commits"  # commits 或 releases
    note: str = ""  # 备注

    @classmethod
    def from_dict(cls, data: Dict) -> "RepoWatchConfig":
        return cls(
            provider=data.get("provider", ""),
            repo=data.get("repo", ""),
            branch=data.get("branch", ""),
            watch_type=data.get("watch_type", data.get("type", "commits")),
            note=data.get("note", "")
        )

    def to_dict(self) -> Dict:
        return {
            "provider": self.provider,
            "repo": self.repo,
            "branch": self.branch,
            "watch_type": self.watch_type,
            "note": self.note
        }

    def get_cache_key(self) -> str:
        """获取缓存键"""
        return f"{self.provider}:{self.repo}:{self.branch}:{self.watch_type}"


@dataclass
class GroupWatchConfig:
    """群组/组织监听配置"""
    provider: str  # github, gitlab, cnb
    group: str  # 组织名/群组名
    watch_type: str = "commits"  # commits 或 releases
    include_repos: List[str] = field(default_factory=list)  # 只监听这些仓库，为空则监听全部
    exclude_repos: List[str] = field(default_factory=list)  # 排除这些仓库
    branch: str = ""  # 默认分支，为空则使用各仓库默认分支
    note: str = ""  # 备注

    @classmethod
    def from_dict(cls, data: Dict) -> "GroupWatchConfig":
        return cls(
            provider=data.get("provider", ""),
            group=data.get("group", data.get("org", data.get("organization", ""))),
            watch_type=data.get("watch_type", data.get("type", "commits")),
            include_repos=data.get("include_repos", data.get("include", [])),
            exclude_repos=data.get("exclude_repos", data.get("exclude", [])),
            branch=data.get("branch", ""),
            note=data.get("note", "")
        )

    def to_dict(self) -> Dict:
        return {
            "provider": self.provider,
            "group": self.group,
            "watch_type": self.watch_type,
            "include_repos": self.include_repos,
            "exclude_repos": self.exclude_repos,
            "branch": self.branch,
            "note": self.note
        }

    def should_watch_repo(self, repo_name: str) -> bool:
        """判断是否应该监听该仓库"""
        # 如果在排除列表中，不监听
        if repo_name in self.exclude_repos:
            return False
        # 如果指定了包含列表，只监听列表中的仓库
        if self.include_repos and repo_name not in self.include_repos:
            return False
        return True


@dataclass
class PushTargetConfig:
    """推送目标配置"""
    groups: List[str] = field(default_factory=list)  # 推送的群聊
    users: List[str] = field(default_factory=list)  # 推送的用户

    @classmethod
    def from_dict(cls, data: Dict) -> "PushTargetConfig":
        return cls(
            groups=data.get("groups", data.get("group", [])),
            users=data.get("users", data.get("user", []))
        )


@dataclass
class WatchTargetConfig:
    """监听目标配置（包含推送目标）"""
    # 监听配置
    repos: List[RepoWatchConfig] = field(default_factory=list)
    groups: List[GroupWatchConfig] = field(default_factory=list)
    
    # 推送目标
    push_targets: PushTargetConfig = field(default_factory=PushTargetConfig)

    @classmethod
    def from_dict(cls, data: Dict) -> "WatchTargetConfig":
        config = cls()
        
        # 解析仓库配置
        repos_data = data.get("repos", data.get("watch_repos", []))
        for repo_data in repos_data:
            config.repos.append(RepoWatchConfig.from_dict(repo_data))
        
        # 解析群组配置
        groups_data = data.get("groups", data.get("watch_groups", []))
        for group_data in groups_data:
            config.groups.append(GroupWatchConfig.from_dict(group_data))
        
        # 解析推送目标
        push_data = {
            "groups": data.get("push_groups", data.get("groups", [])),
            "users": data.get("push_users", data.get("users", []))
        }
        config.push_targets = PushTargetConfig.from_dict(push_data)
        
        return config


@dataclass
class ProviderConfig:
    """提供商配置"""
    name: str
    enabled: bool = True
    token: str = ""
    api_url: str = ""  # 用于自部署实例

    @classmethod
    def from_dict(cls, name: str, data: Dict) -> "ProviderConfig":
        return cls(
            name=name,
            enabled=data.get("enabled", True),
            token=data.get("token", ""),
            api_url=data.get("api_url", data.get("url", ""))
        )


@dataclass
class PluginConfig:
    """插件配置"""
    # 全局设置
    auto_check: bool = False
    check_interval: int = 1800  # 秒
    first_push: bool = False
    
    # 提供商配置
    providers: Dict[str, ProviderConfig] = field(default_factory=dict)
    
    # 默认推送目标（全局）
    push_groups: List[str] = field(default_factory=list)
    push_users: List[str] = field(default_factory=list)
    
    # 仓库监听列表（简化的仓库配置）
    watch_repos: List[RepoWatchConfig] = field(default_factory=list)
    
    # 群组监听列表
    watch_groups: List[GroupWatchConfig] = field(default_factory=list)
    
    # 高级监听配置（包含独立推送目标）
    watch_targets: List[WatchTargetConfig] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict) -> "PluginConfig":
        config = cls()
        
        # 全局设置
        config.auto_check = data.get("auto_check", False)
        config.check_interval = data.get("check_interval", 1800)
        config.first_push = data.get("first_push", False)
        
        # 提供商配置
        provider_names = ["github", "gitlab", "cnb"]
        for name in provider_names:
            if name in data:
                config.providers[name] = ProviderConfig.from_dict(name, data[name])
        
        # 兼容单独的提供商配置字段
        if "github_enabled" in data:
            config.providers["github"] = ProviderConfig(
                name="github",
                enabled=data.get("github_enabled", True),
                token=data.get("github_token", ""),
                api_url=""
            )
        if "gitlab_enabled" in data:
            config.providers["gitlab"] = ProviderConfig(
                name="gitlab",
                enabled=data.get("gitlab_enabled", True),
                token=data.get("gitlab_token", ""),
                api_url=data.get("gitlab_url", "")
            )
        if "cnb_enabled" in data:
            config.providers["cnb"] = ProviderConfig(
                name="cnb",
                enabled=data.get("cnb_enabled", True),
                token=data.get("cnb_token", ""),
                api_url=""
            )
        
        # 全局推送目标
        config._parse_push_targets(data)
        
        # 仓库监听配置
        config._parse_watch_repos(data)
        
        # 群组监听配置
        config._parse_watch_groups(data)
        
        # 高级监听配置
        config._parse_watch_targets(data)
        
        return config

    def _parse_push_targets(self, data: Dict):
        """解析推送目标"""
        for key in ["push_groups", "groups"]:
            if key in data:
                push_groups = data[key]
                if isinstance(push_groups, str):
                    try:
                        self.push_groups = json.loads(push_groups)
                    except:
                        self.push_groups = []
                else:
                    self.push_groups = list(push_groups)
                break
        
        for key in ["push_users", "users"]:
            if key in data:
                push_users = data[key]
                if isinstance(push_users, str):
                    try:
                        self.push_users = json.loads(push_users)
                    except:
                        self.push_users = []
                else:
                    self.push_users = list(push_users)
                break

    def _parse_watch_repos(self, data: Dict):
        """解析仓库监听配置"""
        watch_repos_data = None
        for key in ["watch_repos", "repos"]:
            if key in data:
                watch_repos_data = data[key]
                break
        
        if watch_repos_data:
            if isinstance(watch_repos_data, str):
                try:
                    watch_repos_data = json.loads(watch_repos_data)
                except:
                    watch_repos_data = []
            
            for repo_data in watch_repos_data:
                self.watch_repos.append(RepoWatchConfig.from_dict(repo_data))

    def _parse_watch_groups(self, data: Dict):
        """解析群组监听配置"""
        watch_groups_data = None
        for key in ["watch_groups", "groups"]:
            if key in data:
                # 区分是推送群聊还是监听群组
                if key == "groups" and isinstance(data[key], list):
                    # 可能是推送群聊，跳过
                    continue
                watch_groups_data = data[key]
                break
        
        if watch_groups_data:
            if isinstance(watch_groups_data, str):
                try:
                    watch_groups_data = json.loads(watch_groups_data)
                except:
                    watch_groups_data = []
            
            for group_data in watch_groups_data:
                self.watch_groups.append(GroupWatchConfig.from_dict(group_data))

    def _parse_watch_targets(self, data: Dict):
        """解析高级监听配置"""
        watch_targets_data = data.get("watch_targets", [])
        
        if watch_targets_data:
            if isinstance(watch_targets_data, str):
                try:
                    watch_targets_data = json.loads(watch_targets_data)
                except:
                    watch_targets_data = []
            
            for target_data in watch_targets_data:
                self.watch_targets.append(WatchTargetConfig.from_dict(target_data))

    def get_provider_config(self, provider_name: str) -> Optional[ProviderConfig]:
        """获取提供商配置"""
        return self.providers.get(provider_name.lower())

    def is_provider_enabled(self, provider_name: str) -> bool:
        """检查提供商是否启用"""
        config = self.get_provider_config(provider_name)
        return config.enabled if config else False

    def get_all_push_targets(self) -> tuple:
        """获取所有推送目标"""
        groups = set(self.push_groups)
        users = set(self.push_users)
        
        # 合并高级配置中的推送目标
        for target in self.watch_targets:
            groups.update(target.push_targets.groups)
            users.update(target.push_targets.users)
        
        return list(groups), list(users)
