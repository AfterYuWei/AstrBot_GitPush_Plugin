"""
Git 服务提供商模块
"""
# 使用延迟导入避免循环依赖问题
from .base import (
    BaseGitProvider,
    CommitInfo,
    ReleaseInfo,
    RepoInfo,
)

# 具体实现延迟加载
_GitHubProvider = None
_GitLabProvider = None
_CNBProvider = None


def _get_github_provider():
    global _GitHubProvider
    if _GitHubProvider is None:
        try:
            from .github import GitHubProvider as _GH
            _GitHubProvider = _GH
        except ImportError:
            pass
    return _GitHubProvider


def _get_gitlab_provider():
    global _GitLabProvider
    if _GitLabProvider is None:
        try:
            from .gitlab import GitLabProvider as _GL
            _GitLabProvider = _GL
        except ImportError:
            pass
    return _GitLabProvider


def _get_cnb_provider():
    global _CNBProvider
    if _CNBProvider is None:
        try:
            from .cnb import CNBProvider as _CNB
            _CNBProvider = _CNB
        except ImportError:
            pass
    return _CNBProvider


# 属性访问
def __getattr__(name):
    if name == "GitHubProvider":
        return _get_github_provider()
    if name == "GitLabProvider":
        return _get_gitlab_provider()
    if name == "CNBProvider":
        return _get_cnb_provider()
    if name == "PROVIDER_MAP":
        pm = {}
        gh = _get_github_provider()
        gl = _get_gitlab_provider()
        cnb = _get_cnb_provider()
        if gh:
            pm["github"] = gh
        if gl:
            pm["gitlab"] = gl
        if cnb:
            pm["cnb"] = cnb
        return pm
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseGitProvider",
    "CommitInfo",
    "ReleaseInfo",
    "RepoInfo",
    "GitHubProvider",
    "GitLabProvider",
    "CNBProvider",
    "PROVIDER_MAP",
]


def create_provider(provider_type: str, token: str = "", api_url: str = "", **kwargs):
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
    provider_map = __getattr__("PROVIDER_MAP")
    provider_class = provider_map.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"不支持的提供商类型: {provider_type}")
    return provider_class(token=token, api_url=api_url, **kwargs)
