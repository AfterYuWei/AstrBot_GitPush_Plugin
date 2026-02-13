"""
Git 服务提供商模块
"""
# 基础类型（无外部依赖，安全导入）
from .base import (
    BaseGitProvider,
    CommitInfo,
    ReleaseInfo,
    RepoInfo,
)

# 具体实现（可能依赖网络库）
try:
    from .github import GitHubProvider
except ImportError:
    GitHubProvider = None  # type: ignore

try:
    from .gitlab import GitLabProvider
except ImportError:
    GitLabProvider = None  # type: ignore

try:
    from .cnb import CNBProvider
except ImportError:
    CNBProvider = None  # type: ignore

__all__ = [
    "BaseGitProvider",
    "CommitInfo",
    "ReleaseInfo",
    "RepoInfo",
    "GitHubProvider",
    "GitLabProvider",
    "CNBProvider",
]

# 提供商映射（排除未成功导入的）
PROVIDER_MAP = {}
if GitHubProvider:
    PROVIDER_MAP["github"] = GitHubProvider
if GitLabProvider:
    PROVIDER_MAP["gitlab"] = GitLabProvider
if CNBProvider:
    PROVIDER_MAP["cnb"] = CNBProvider


def create_provider(provider_type: str, token: str = "", api_url: str = "", **kwargs) -> BaseGitProvider:
    """
    创建提供商实例
    
    Args:
        provider_type: 提供商类型 (github, gitlab, cnb)
        token: 访问令牌
        api_url: API 地址（用于自部署实例）
        **kwargs: 其他配置
    
    Returns:
        提供商实例
    """
    provider_class = PROVIDER_MAP.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"不支持的提供商类型: {provider_type}")
    return provider_class(token=token, api_url=api_url, **kwargs)
