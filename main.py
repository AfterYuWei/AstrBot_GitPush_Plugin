"""
AstrBot Git仓库推送插件
支持 GitHub、GitLab、CNB 的仓库更新推送

功能特性:
- 模块化设计，各提供商独立实现
- GitLab 支持自部署实例
- 多提供商同时监听
- 支持 commits 和 releases 两种监听类型
- 支持仓库级别和群组级别监听
"""
import asyncio
from typing import Optional, Dict, List, Set

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

from .providers import (
    BaseGitProvider,
    CommitInfo,
    ReleaseInfo,
    RepoInfo,
    GitHubProvider,
    GitLabProvider,
    CNBProvider,
    PROVIDER_MAP,
)
from .utils import (
    PluginConfig, 
    RepoWatchConfig, 
    GroupWatchConfig,
    DataStorage, 
    UpdateCache
)


@register("astrbot_plugin_git_push", "YourName", "Git仓库推送插件", "1.0.0")
class GitPushPlugin(Star):
    """Git仓库推送插件主类"""

    def __init__(self, context: Context):
        super().__init__(context)
        self.config: Optional[PluginConfig] = None
        self.storage: Optional[DataStorage] = None
        self.cache: Optional[UpdateCache] = None
        self.providers: Dict[str, BaseGitProvider] = {}
        self._check_task: Optional[asyncio.Task] = None
        self._running = False
        # 动态仓库列表（从群组展开）
        self._expanded_repos: Dict[str, RepoWatchConfig] = {}

    async def initialize(self):
        """初始化插件"""
        # 加载配置
        raw_config = self._load_config()
        self.config = PluginConfig.from_dict(raw_config)
        
        # 初始化存储
        data_dir = self.context.get_data_dir()
        self.storage = DataStorage(data_dir)
        self.cache = UpdateCache(self.storage)
        
        # 初始化提供商
        await self._init_providers()
        
        # 展开群组配置
        await self._expand_group_configs()
        
        # 启动自动检查
        if self.config.auto_check:
            self._start_auto_check()
        
        logger.info(f"Git推送插件初始化完成")
        logger.info(f"已启用提供商: {list(self.providers.keys())}")
        logger.info(f"监听仓库数: {len(self.config.watch_repos) + len(self._expanded_repos)}")

    def _load_config(self) -> Dict:
        """加载配置"""
        config = {}
        
        try:
            if hasattr(self.context, 'get_config'):
                config = self.context.get_config() or {}
        except:
            pass
        
        if not config:
            try:
                import os
                import json
                config_file = os.path.join(self.context.get_data_dir(), "config.json")
                if os.path.exists(config_file):
                    with open(config_file, "r", encoding="utf-8") as f:
                        config = json.load(f)
            except:
                pass
        
        return config

    async def _init_providers(self):
        """初始化提供商"""
        self.providers = {}
        
        provider_names = ["github", "gitlab", "cnb"]
        
        for name in provider_names:
            config = self.config.get_provider_config(name)
            if config and config.enabled:
                provider_class = PROVIDER_MAP.get(name)
                if provider_class is None:
                    logger.warn(f"{name} 提供商模块加载失败，跳过")
                    continue
                
                self.providers[name] = provider_class(
                    token=config.token,
                    api_url=config.api_url
                )
                await self.providers[name].init()
                logger.info(f"{name} 提供商已初始化")

    async def _expand_group_configs(self):
        """展开群组配置为具体的仓库列表"""
        self._expanded_repos = {}
        
        for group_config in self.config.watch_groups:
            provider_name = group_config.provider.lower()
            
            if provider_name not in self.providers:
                logger.warn(f"群组 {group_config.group} 的提供商 {group_config.provider} 未启用")
                continue
            
            provider = self.providers[provider_name]
            
            try:
                repos = await provider.get_group_repos(group_config.group)
                logger.info(f"从 {group_config.provider}/{group_config.group} 获取到 {len(repos)} 个仓库")
                
                for repo_info in repos:
                    # 检查是否在包含/排除列表中
                    if not group_config.should_watch_repo(repo_info.repo_name):
                        continue
                    
                    # 创建仓库监听配置
                    repo_config = RepoWatchConfig(
                        provider=group_config.provider,
                        repo=repo_info.name,
                        branch=group_config.branch or repo_info.default_branch,
                        watch_type=group_config.watch_type,
                        note=group_config.note
                    )
                    
                    # 使用缓存键作为唯一标识
                    cache_key = repo_config.get_cache_key()
                    self._expanded_repos[cache_key] = repo_config
                
                # 缓存群组仓库列表
                self.cache.set_group_cached_repos(
                    group_config.provider,
                    group_config.group,
                    {r.name for r in repos}
                )
                
            except Exception as e:
                logger.error(f"获取群组 {group_config.group} 仓库失败: {e}")

    def _start_auto_check(self):
        """启动自动检查"""
        self._running = True
        self._check_task = asyncio.create_task(self._auto_check_loop())
        logger.info(f"已启动自动检查，间隔: {self.config.check_interval}秒")

    async def _auto_check_loop(self):
        """自动检查循环"""
        interval = self.config.check_interval
        while self._running:
            try:
                await asyncio.sleep(interval)
                if self._running:
                    await self._check_and_push()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"自动检查出错: {e}")

    async def terminate(self):
        """销毁插件"""
        self._running = False
        if self._check_task:
            self._check_task.cancel()
        for provider in self.providers.values():
            await provider.close()
        logger.info("Git推送插件已卸载")

    async def _check_and_push(self, silent: bool = False) -> int:
        """检查并推送更新"""
        all_repos = list(self.config.watch_repos) + list(self._expanded_repos.values())
        
        if not all_repos:
            if not silent:
                logger.warn("未配置监听仓库")
            return 0

        update_count = 0
        all_updates = []

        for repo_config in all_repos:
            provider_name = repo_config.provider.lower()
            
            if provider_name not in self.providers:
                continue
            
            provider = self.providers[provider_name]
            
            try:
                if repo_config.watch_type == "commits":
                    update_info = await self._check_commits(provider, repo_config)
                else:
                    update_info = await self._check_release(provider, repo_config)
                
                if update_info:
                    all_updates.append({
                        "info": update_info,
                        "note": repo_config.note
                    })
                    update_count += 1
            except Exception as e:
                logger.error(f"检查 {repo_config.provider}/{repo_config.repo} 失败: {e}")

        # 推送消息
        for update in all_updates:
            message = update["info"].to_push_message()
            if update["note"]:
                message += f"\n📌 备注: {update['note']}"
            await self._send_push(message)

        return update_count

    async def _check_commits(self, provider: BaseGitProvider, repo_config: RepoWatchConfig) -> Optional[CommitInfo]:
        """检查提交更新"""
        repo = repo_config.repo
        branch = repo_config.branch
        
        commit = await provider.get_latest_commit(repo, branch)
        if not commit:
            return None
        
        cached_sha = self.cache.get_cached_commit_sha(
            repo_config.provider, repo, commit.branch
        )
        
        is_first = self.cache.is_first_commit_check(
            repo_config.provider, repo, commit.branch
        )
        
        if commit.sha == cached_sha:
            return None
        
        self.cache.set_cached_commit_sha(
            repo_config.provider, repo, commit.branch, commit.sha
        )
        
        if is_first and not self.config.first_push:
            logger.info(f"首次检测到 {repo_config.provider}/{repo}，跳过推送")
            return None
        
        logger.info(f"检测到更新: {repo_config.provider}/{repo} - {commit.sha[:7]}")
        return commit

    async def _check_release(self, provider: BaseGitProvider, repo_config: RepoWatchConfig) -> Optional[ReleaseInfo]:
        """检查发布更新"""
        repo = repo_config.repo
        
        release = await provider.get_latest_release(repo)
        if not release:
            return None
        
        cached_tag = self.cache.get_cached_release_tag(repo_config.provider, repo)
        is_first = self.cache.is_first_release_check(repo_config.provider, repo)
        
        if release.tag == cached_tag:
            return None
        
        self.cache.set_cached_release_tag(repo_config.provider, repo, release.tag)
        
        if is_first and not self.config.first_push:
            logger.info(f"首次检测到 {repo_config.provider}/{repo} release，跳过推送")
            return None
        
        logger.info(f"检测到新版本: {repo_config.provider}/{repo} - {release.tag}")
        return release

    async def _send_push(self, message: str):
        """发送推送消息"""
        groups, users = self.config.get_all_push_targets()
        
        for group_id in groups:
            try:
                await self.context.send_message(
                    message,
                    target_type="group",
                    target_id=str(group_id)
                )
                logger.info(f"已推送到群: {group_id}")
            except Exception as e:
                logger.error(f"推送到群 {group_id} 失败: {e}")

        for user_id in users:
            try:
                await self.context.send_message(
                    message,
                    target_type="private",
                    target_id=str(user_id)
                )
                logger.info(f"已推送到用户: {user_id}")
            except Exception as e:
                logger.error(f"推送到用户 {user_id} 失败: {e}")

    # ============ 指令部分 ============

    @filter.command("git_push_help")
    async def show_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """📖 Git推送插件帮助

🔹 基础指令:
  /git_push_help - 显示帮助
  /git_push_check - 检查仓库更新
  /git_push_status - 查看当前状态
  /git_push_list - 列出监听的仓库和群组
  /git_push_providers - 查看提供商状态
  /git_push_refresh - 刷新群组仓库列表

🔹 监听配置:
  1. 仓库级别：监听单个仓库
  2. 群组级别：监听整个组织/群组下的所有仓库

🔹 配置示例:

  仓库监听 (watch_repos):
[
  {
    "provider": "github",
    "repo": "owner/repo",
    "branch": "main",
    "watch_type": "commits",
    "note": "备注"
  }
]

  群组监听 (watch_groups):
[
  {
    "provider": "github",
    "group": "organization-name",
    "watch_type": "commits",
    "include_repos": [],
    "exclude_repos": ["test-repo"],
    "note": "整个组织"
  }
]

🔹 获取令牌:
  GitHub: https://github.com/settings/tokens
  GitLab: https://gitlab.com/-/profile/personal_access_tokens
  CNB: https://cnb.cool/-/profile/personal_access_tokens
"""
        yield event.plain_result(help_text)

    @filter.command("git_push_check")
    async def check_update(self, event: AstrMessageEvent):
        """手动检查仓库更新"""
        yield event.plain_result("正在检查仓库更新...")

        try:
            count = await self._check_and_push()
            if count > 0:
                yield event.plain_result(f"✅ 检查完成，发现 {count} 个仓库有更新")
            else:
                yield event.plain_result("✅ 检查完成，没有发现仓库更新")
        except Exception as e:
            logger.error(f"检查更新失败: {e}")
            yield event.plain_result(f"❌ 检查失败: {e}")

    @filter.command("git_push_status")
    async def show_status(self, event: AstrMessageEvent):
        """查看当前状态"""
        text = "📊 Git推送插件状态\n\n"
        
        text += f"🔄 自动检查: {'✅ 开启' if self.config.auto_check else '❌ 关闭'}\n"
        if self.config.auto_check:
            text += f"   间隔: {self.config.check_interval} 秒\n"
        
        text += f"🔔 首次推送: {'✅ 开启' if self.config.first_push else '❌ 关闭'}\n\n"
        
        groups, users = self.config.get_all_push_targets()
        text += f"📢 推送群聊: {len(groups)} 个\n"
        text += f"📢 推送用户: {len(users)} 个\n\n"
        
        text += f"📦 直接监听仓库: {len(self.config.watch_repos)} 个\n"
        text += f"📂 监听群组: {len(self.config.watch_groups)} 个\n"
        text += f"📦 群组展开仓库: {len(self._expanded_repos)} 个\n"
        
        yield event.plain_result(text)

    @filter.command("git_push_providers")
    async def show_providers(self, event: AstrMessageEvent):
        """查看提供商状态"""
        text = "🔌 提供商状态\n\n"
        
        providers_status = {
            "github": ("GitHub", self.config.get_provider_config("github")),
            "gitlab": ("GitLab", self.config.get_provider_config("gitlab")),
            "cnb": ("CNB", self.config.get_provider_config("cnb")),
        }
        
        for name, (display_name, config) in providers_status.items():
            if config and config.enabled:
                token_status = "✅ 已配置" if config.token else "⚠️ 未配置"
                url_info = f" ({config.api_url})" if config.api_url else ""
                text += f"✅ {display_name}{url_info}\n"
                text += f"   令牌: {token_status}\n"
            else:
                text += f"❌ {display_name}\n"
                text += f"   状态: 未启用\n"
            text += "\n"
        
        yield event.plain_result(text)

    @filter.command("git_push_list")
    async def list_repos(self, event: AstrMessageEvent):
        """列出监听的仓库和群组"""
        text = "📋 监听配置列表\n\n"
        
        # 仓库列表
        if self.config.watch_repos:
            text += "🔹 直接监听仓库:\n"
            for i, repo in enumerate(self.config.watch_repos, 1):
                status = "✅" if repo.provider.lower() in self.providers else "❌"
                text += f"  {status} [{i}] {repo.provider}/{repo.repo}\n"
                text += f"       类型: {repo.watch_type}"
                if repo.branch:
                    text += f" | 分支: {repo.branch}"
                text += "\n"
            text += "\n"
        
        # 群组列表
        if self.config.watch_groups:
            text += "🔹 监听群组:\n"
            for i, group in enumerate(self.config.watch_groups, 1):
                status = "✅" if group.provider.lower() in self.providers else "❌"
                text += f"  {status} [{i}] {group.provider}/{group.group}\n"
                text += f"       类型: {group.watch_type}"
                if group.include_repos:
                    text += f" | 包含: {len(group.include_repos)}"
                if group.exclude_repos:
                    text += f" | 排除: {len(group.exclude_repos)}"
                text += "\n"
            text += "\n"
        
        # 展开的仓库
        if self._expanded_repos:
            text += f"🔹 群组展开仓库 ({len(self._expanded_repos)} 个):\n"
            for i, (key, repo) in enumerate(self._expanded_repos.items(), 1):
                if i > 10:
                    text += f"  ... 还有 {len(self._expanded_repos) - 10} 个\n"
                    break
                text += f"  [{i}] {repo.provider}/{repo.repo}\n"
        
        if not self.config.watch_repos and not self.config.watch_groups:
            text = "📋 当前没有监听任何仓库或群组"
        
        yield event.plain_result(text)

    @filter.command("git_push_refresh")
    async def refresh_groups(self, event: AstrMessageEvent):
        """刷新群组仓库列表"""
        yield event.plain_result("正在刷新群组仓库列表...")
        
        try:
            await self._expand_group_configs()
            yield event.plain_result(f"✅ 刷新完成，共展开 {len(self._expanded_repos)} 个仓库")
        except Exception as e:
            logger.error(f"刷新群组失败: {e}")
            yield event.plain_result(f"❌ 刷新失败: {e}")
