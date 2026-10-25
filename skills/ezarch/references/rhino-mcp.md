# Rhino 官方 MCP：文档操作与接入

McNeel 的 **Rhino MCP Platform / RhinoAI** 可连接当前 Rhino 文档，调用原生几何、脚本、Grasshopper 和视口能力；Yak 包名为 **Rhino-MCP-Platform**。已有可用连接可直接复用。仅需离线读写 3DM 时，见 [rhino3dm 接口](edit-existing.md#rhino-文件与精确实体)。

## 当前文档与会话

从当前客户端的工具描述中查找会话列表和只读上下文工具，前缀不一定叫 `rhino`。用返回的真实 slot/会话标识读取文件名、单位、图层、对象和视口；多个会话按文件名、版本、端口匹配目标，无法确定时再询问。不硬编码测试时的 slot、PID 或端口。

| 观察结果 | 能说明什么 |
|---|---|
| Yak 中已安装、MCPConnect 显示 Installed | 插件文件或客户端配置存在，不等于已连接目标文档 |
| Router 初始化、工具列表成功 | 客户端能发现工具，仍可能没有 Rhino 会话 |
| 会话列表为空 | 检查 Rhino 是否开启、是否运行 MCPStart；不要用自动创建窗口的工具代替状态查询 |
| 指定会话可读取文档 | 控制通道可用；空文档对象数为 0 是正常结果 |

`MCPConnect` 用于客户端配置；目标 Rhino 文档开启时运行 `MCPStart` 启动服务，端口以命令输出为准。支持 `MCPStatus` 的版本可用它查看状态。后续操作持续指向选定会话；新建 Rhino 窗口需符合用户请求。

## 原生操作与保存

- 使用当前 MCP 暴露的几何、命令、Python/C# 工具。脚本以工具注入的 `__rhino_doc__` 为目标，不依赖可能变化的 `ActiveDoc` 或 `rhinoscriptsyntax` 的隐式文档。
- 按对象 ID、图层或选择定位，读取文档单位和容差；局部编辑保留未涉及对象，可使用撤销记录。长脚本按工具超时拆分，不因等待而重复提交同一操作。
- 需要精确实体时，读取实际几何类型、`IsValid`、`IsSolid` 和布尔返回对象；网格或开口曲面不等于闭合 BRep。
- 可保存可继续编辑的 `.3dm`，按修改范围回读单位、对象和属性。连接探测使用只读操作，无需创建测试几何或清空文档。

## 视口与渲染

视口工具可选择相机、观察范围和显示模式，也可用 Rhino 原生视口捕获保存图像。MCP 图片有时嵌套在文本 JSON 的 content 中，需解析后交给图像查看能力，不把 base64 当正文输出。视图用于理解、推敲和检查模型，见 [视觉判断](viewing-editing.md)。

AI 驱动 Rhino 渲染有反复失败、消耗较多时间和 token 的实际反馈。尝试前简要说明风险，已有知情授权无需重复确认；失败后没有新的排障依据时，不反复重试。

## 安装与兼容性

仅在连接缺失或需要修复时处理。需要已安装、获许可且兼容的 Rhino；Rhino MCP 与 EZarch 的 Python/Blender 环境独立。以下兼容信息核对于 2026-10-25，安装时以当前官方说明和实际包为准。

- 官方插件需要 .NET Core，不支持 .NET Framework；当前故障页列明不支持 Intel Mac。运行时切换对其他插件的影响见 [官方说明](https://developer.rhino3d.com/guides/rhinocommon/moving-to-dotnet-core/)。
- Router 默认目标为 Rhino 8；Rhino 9 需匹配实际启动参数。Grasshopper 2 工具需要 Rhino 9 WIP/BETA。
- Windows 可从 `HKLM` / `HKCU` 的 `SOFTWARE\McNeel\Rhinoceros\<版本>\Install` 查 `Path`、`InstallPath`，核对实际 `Rhino.exe` 和同目录 `Yak.exe`，不假定安装在 C 盘。
- macOS 从实际 `.app` 定位自带 Yak；常见位置为 `/Applications/Rhino 8.app/Contents/Resources/bin/yak`。系统、架构和 Rhino 版本需与包匹配。

用目标 Rhino 自带 Yak 查询已安装和兼容版本；以下 PowerShell 中的 `$yak`、`$packageVersion` 取自实际路径和查询结果：

```powershell
& $yak help install
& $yak list
& $yak search Rhino-MCP-Platform
& $yak install --source=https://yak.rhino3d.com/ Rhino-MCP-Platform $packageVersion
if ($LASTEXITCODE -ne 0) { throw 'Rhino MCP installation failed; inspect the Yak error.' }
& $yak list
```

macOS 使用对应可执行文件和相同 Yak 参数，shell 语法另行适配。已有可用版本无需重装；安装位置以 Yak 返回的目标 Rhino 用户包目录为准。核对包与对应架构 Router；插件加载确需重启 Rhino 时，保留未保存文档。

客户端连接需要的 Router 路径、参数及配置格式见 [客户端配置](rhino-mcp-clients.md)。

## 连接与安装排障

- **客户端缺少工具**：`MCPConnect` 提供实际 Router 路径和配置；客户端重载后查看工具列表。`Not detected` 仅表示未自动检测到，不等于不支持。
- **工具可用但没有文档**：查看会话列表、Rhino 的 MCPStart 输出及目标版本。连接恢复后复用该会话，无需重装。
- **网络或安装失败**：按 Yak 错误区分网络权限、代理/证书、源服务、包兼容性和 Rhino 许可；公开包下载失败不一定需要登录。条件没有变化时不重复登录、重装或改写相同配置。
- **目标机器不能联网**：可从获准环境取得官方兼容 `.yak`，核对来源、版本及提供的校验信息，再用 `yak install <本地包路径>` 安装。不要猜 CDN 地址或假设源码仓库必有二进制 Releases。
- **跨主机连接**：stdio Router 与 Rhino 要在可访问同一本机环境的宿主运行。云端客户端的 localhost 不指向用户电脑；HTTP 接入需核对官方实际支持的传输与地址，不能直接把本地服务暴露到公网。
- **操作成功但看不到对象**：确认目标窗口、图层可见性和视图范围，可用 Zoom Extents 定位；对象数量或命令成功不能代替实际看图。

## 官方资料

- [Rhino MCP Platform](https://mcneel.github.io/RhinoAI/) · [客户端入门](https://mcneel.github.io/RhinoAI/docs/getting-started/) · [兼容性与故障排查](https://mcneel.github.io/RhinoAI/docs/troubleshooting/)
- [Yak CLI：安装、包源与本地包](https://developer.rhino3d.com/guides/yak/yak-cli-reference/)
- [MCPConnect / MCPStart / MCPStatus](https://docs.mcneel.com/rhino/9/help/en-us/commands/mcpstatus.htm)（Rhino 9 文档；其他版本以实际插件为准）
