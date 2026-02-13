# AstrBot Git仓库推送插件

一个模块化的 Git 仓库更新推送插件，支持 GitHub、GitLab（含自部署）、CNB 多平台同时监听。

## 功能特性

- ✅ **模块化设计** - 各 Git 服务提供商独立实现，易于扩展
- ✅ **多平台支持** - GitHub、GitLab、CNB 可同时监听
- ✅ **自部署支持** - GitLab 支持自定义 API 地址
- ✅ **双监听模式** - 支持 commits（提交）和 releases（发布）
- ✅ **双维度监听** - 支持仓库级别和群组/组织级别监听
- ✅ **自动检查** - 可配置定时自动检查更新
- ✅ **可视化配置** - 所有配置项可在 AstrBot WebUI 中设置
- ✅ **灵活推送** - 支持推送到群聊和私聊

## 安装

将插件文件夹放入 AstrBot 的 `plugins` 目录下，重启 AstrBot 即可。

## 配置

所有配置可在 AstrBot WebUI 的「插件管理 → 配置」页面进行设置。

### 配置项说明

#### 全局设置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `auto_check` | 是否开启自动检查更新 | `false` |
| `check_interval` | 自动检查间隔（秒） | `1800` (30分钟) |
| `first_push` | 首次添加仓库时是否推送 | `false` |

#### GitHub 配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `github_enabled` | 是否启用 GitHub 监听 | `true` |
| `github_token` | 访问令牌（可选） | 空 |

#### GitLab 配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `gitlab_enabled` | 是否启用 GitLab 监听 | `true` |
| `gitlab_url` | GitLab API 地址 | `https://gitlab.com/api/v4` |
| `gitlab_token` | 访问令牌（可选） | 空 |

> 💡 **自部署 GitLab**: 将 `gitlab_url` 改为你的实例地址，如 `https://gitlab.example.com/api/v4`

#### CNB 配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `cnb_enabled` | 是否启用 CNB 监听 | `true` |
| `cnb_token` | 访问令牌（可选） | 空 |

#### 推送目标

| 配置项 | 说明 | 格式 |
|--------|------|------|
| `push_groups` | 推送的群聊ID列表 | JSON 数组，如 `["123456", "789012"]` |
| `push_users` | 推送的用户ID列表 | JSON 数组，如 `["111111", "222222"]` |

### 监听配置

#### 1. 仓库级别监听 (`watch_repos`)

监听单个仓库的更新：

```json
[
  {
    "provider": "github",
    "repo": "Soulter/astrbot",
    "branch": "main",
    "watch_type": "commits",
    "note": "AstrBot主仓库"
  },
  {
    "provider": "gitlab",
    "repo": "group/project",
    "branch": "",
    "watch_type": "releases",
    "note": ""
  }
]
```

| 字段 | 说明 | 必填 |
|------|------|------|
| `provider` | 提供商: `github`、`gitlab`、`cnb` | ✅ |
| `repo` | 仓库名，格式: `owner/repo` | ✅ |
| `branch` | 分支名，为空使用默认分支 | ❌ |
| `watch_type` | 监听类型: `commits` 或 `releases` | ❌ |
| `note` | 备注说明 | ❌ |

#### 2. 群组级别监听 (`watch_groups`)

监听整个组织/群组下的所有仓库：

```json
[
  {
    "provider": "github",
    "group": "AstrBotDevs",
    "watch_type": "commits",
    "include_repos": [],
    "exclude_repos": ["test-repo"],
    "branch": "",
    "note": "AstrBot开发组所有仓库"
  },
  {
    "provider": "gitlab",
    "group": "my-group",
    "watch_type": "releases",
    "include_repos": ["important-project"],
    "exclude_repos": [],
    "note": "只监听important-project"
  }
]
```

| 字段 | 说明 | 必填 |
|------|------|------|
| `provider` | 提供商: `github`、`gitlab`、`cnb` | ✅ |
| `group` | 组织名/群组名 | ✅ |
| `watch_type` | 监听类型: `commits` 或 `releases` | ❌ |
| `include_repos` | 只监听这些仓库，为空监听全部 | ❌ |
| `exclude_repos` | 排除这些仓库 | ❌ |
| `branch` | 默认分支，为空使用各仓库默认分支 | ❌ |
| `note` | 备注说明 | ❌ |

> 💡 **提示**: `include_repos` 和 `exclude_repos` 只需要填写仓库名（不含 owner/group）

## 指令列表

| 指令 | 说明 |
|------|------|
| `/git_push_help` | 显示帮助信息 |
| `/git_push_check` | 手动检查仓库更新 |
| `/git_push_status` | 查看插件状态 |
| `/git_push_providers` | 查看提供商状态 |
| `/git_push_list` | 列出监听的仓库和群组 |
| `/git_push_refresh` | 刷新群组仓库列表 |

## 获取访问令牌

配置访问令牌可以提高 API 请求限制：

| 平台 | 获取地址 |
|------|----------|
| GitHub | https://github.com/settings/tokens |
| GitLab | https://gitlab.com/-/profile/personal_access_tokens |
| CNB | https://cnb.cool/-/profile/personal_access_tokens |

## 项目结构

```
git-push-plugin/
├── main.py              # 主入口
├── metadata.yaml        # 插件元数据和配置定义
├── providers/           # Git 服务提供商模块
│   ├── __init__.py
│   ├── base.py          # 基类定义
│   ├── github.py        # GitHub 实现
│   ├── gitlab.py        # GitLab 实现（支持自部署）
│   └── cnb.py           # CNB 实现
├── utils/               # 工具模块
│   ├── __init__.py
│   ├── config.py        # 配置管理
│   └── storage.py       # 数据存储
└── README.md
```

## 扩展新提供商

要添加新的 Git 服务提供商：

1. 在 `providers/` 目录下创建新文件，如 `gitea.py`
2. 继承 `BaseGitProvider` 基类
3. 实现必需的方法
4. 在 `providers/__init__.py` 中注册

```python
# providers/gitea.py
from .base import BaseGitProvider, CommitInfo, ReleaseInfo, RepoInfo

class GiteaProvider(BaseGitProvider):
    @property
    def name(self) -> str:
        return "Gitea"
    
    async def get_group_repos(self, group: str) -> List[RepoInfo]:
        # 实现获取组织仓库...
        pass
    
    # 实现其他方法...
```

## 注意事项

1. 未认证用户访问 GitHub API 有频率限制（每小时 60 次），建议配置 Token
2. 认证用户 GitHub API 限制为每小时 5000 次
3. 自动检查间隔建议不低于 10 分钟，避免频繁请求
4. 群组监听会在插件初始化时获取所有仓库，之后使用 `/git_push_refresh` 刷新
5. 持久化数据存储在 AstrBot 的 data 目录下

## 许可证

MIT License
