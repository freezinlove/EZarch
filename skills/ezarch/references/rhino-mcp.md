# Rhino 官方 MCP：安装、连接、启动与建模

用于在 Rhino 当前文档中建模、修改对象或操作 Grasshopper。优先使用 McNeel 的 **Rhino MCP Platform / RhinoAI**，Yak 包名为 **Rhino-MCP-Platform**。用户指定的 AI 客户端负责调用 MCP；不要求使用 Codex，也不先自建桥接。离线 `rhino3dm` 文件读写继续走 [原生编辑](edit-existing.md#rhino-文件与精确实体)。

## Rhino 渲染出图的暂行限制

Rhino 建模可正常开展。暂不默认由 AI 操控 Rhino 渲染出图，也不主动把 Rhino 建模与自动渲染安排为一条连续交付流程。此限制适用于建模后出图及已有模型出图，包括内置渲染器、渲染插件，以及通过 MCP、脚本或界面发起的渲染；以效果图交付为目的启用渲染视口并捕获图像，也不能绕过此规则。普通建模验收所需的视口截图可以使用，但不能冒充正式渲染成果。

用户要求 AI 使用 Rhino 渲染出图时，按以下顺序处理：

1. **先提示并建议不使用。** 明确说明此方式可能因截图、接口排障和反复尝试消耗大量 token，仍无法完成渲染出图；建议保留可编辑模型，改由用户在 Rhino 中手动渲染。等待用户决定，不能在等待期间启动试渲染或为出图开展专项排障。
2. **第一次坚持后再次确认。** 用户在上述风险提示后第一次明确表示仍要使用 AI 操控 Rhino 渲染时，简短重申高消耗与无法完成的风险，并等待用户第二次明确确认。
3. **第二次确认后执行。** 只有用户在再次提醒后仍明确确认，才继续本次渲染任务。已完成这两次风险确认的同一任务，不逐张图片重复询问；确认不代表无限重试，也不扩大到未授权的系统配置修改。

原始的“建模并渲染”请求、建模授权、设计方案确认、跳过方案确认，或未明确指向渲染的“继续”，均不能替代风险提示后的两次明确确认。此项独立于主 skill 的设计方案确认；已有授权是否充分，应以本次渲染风险确认的实际对话为准。

建模与渲染混合任务中，及时提出上述风险提示；可以按既有授权继续建模、检查和保存模型，仅挂起渲染部分。不得因本限制擅自改用 Blender、生成式图像或其他应用出图；替代方案按用户选择执行。

官方资料核对日期：2026-10-23。包版本、兼容条件和客户端界面可能变化，安装或处理不兼容时重新核对当前官方文档及实际包；不把本次实测版本当成永久固定版本。

## 1. 先识别当前状态

发现当前客户端已有的 Rhino MCP 工具，按描述找会话列表与只读上下文工具；工具前缀不一定叫 `rhino`。先列会话，再用返回的真实 slot/会话标识读取文档、对象数、图层、单位、当前视口及必要的选中对象。已有可用连接就直接进入建模，不重复安装或改客户端配置。

| 观察结果 | 实际含义与下一步 |
|---|---|
| PackageManager/Yak 中已安装 | 插件文件已安装，仍需确认 Rhino 内加载和客户端连接 |
| MCPConnect 中客户端显示 Installed | 该客户端的连接配置已写入，不能据此宣称 Rhino 已启动服务 |
| MCP 初始化与工具列表成功 | Router 可运行、客户端能发现工具，仍需发现实际 Rhino 会话 |
| 会话列表为空 | 检查 Rhino 是否开启、是否运行 MCPStart；不调用可能自动创建新窗口的上下文工具来冒充连接成功 |
| 能用指定会话读到文档 | Rhino 控制通道已验证；空文档对象数为 0 是正常结果 |
| 在 Rhino 中建模并检查、保存回读通过 | 只能宣称对应模型和检查项目已验证，不推广为所有建模操作都可靠 |

若工具尚未加载，先检查本机 Rhino 和用户选定的客户端。客户端不明且影响配置时只询问使用哪一个；不要默认安装其他客户端。用户的建模/安装授权按会话延续；只询问兼容性不等于允许安装或更改配置。需要的网络、用户插件目录写入或应用启动权限由当前宿主的授权机制处理，不通过关闭保护或鉴权来解决。

## 2. 定位 Rhino，核对兼容性

- 需要已安装、获许可且与包兼容的 Rhino。核对主版本、小版本、系统架构、运行时及官方包分发要求。Rhino 7 的安装路径不能作为 Rhino 8 插件目标。
- Windows 可从 `HKLM` / `HKCU` 的 `SOFTWARE\McNeel\Rhinoceros\<版本>\Install` 查 `Path`、`InstallPath`，再核对实际 `Rhino.exe` 和同目录 `Yak.exe`。不要假设装在 C 盘或当前用户叫 admin。
- macOS 从实际 Rhino `.app` 查找自带 Yak；默认例为 `/Applications/Rhino 8.app/Contents/Resources/bin/yak`，以实际应用和当前 [Yak CLI 安装文档](https://developer.rhino3d.com/guides/yak/yak-cli-reference/) 为准。不要把 Windows 注册表、exe 路径和命令用于 macOS。
- 官方插件需要 .NET Core，不支持 .NET Framework 模式。Rhino 8.20 默认使用 .NET 8.0.14 或更高；核对本机实际运行时和包目标，不仅凭 `net8.0` 目录要求升级 Rhino。必要时按 [官方运行时说明](https://developer.rhino3d.com/guides/rhinocommon/moving-to-dotnet-core/) 处理；持久切换运行时可能影响已有插件，不能在未判断影响时修改全局设置。
- 截至上述核对日期，官方故障页明确不支持 Intel Mac；其他架构、较旧 Rhino 与后续版本仍要核对实际分发。Router 默认目标为 Rhino 8，Rhino 9 按实际包和启动参数选择；Grasshopper 2 工具需要 Rhino 9 WIP/BETA。Windows x64 的实测不能作为其他平台验收。没有兼容包时说明具体缺项，保留可行的文件/脚本路线，不反复盲装。

Rhino MCP 与 Blender、ezarch 的 Python 环境独立。仅连接 Rhino 不要求先跑 ezarch 的 `all` bootstrap，也不需要安装 Blender、CadQuery 或替换系统 Python。

## 3. 从 McNeel 官方包源安装

先用目标 Rhino 自带 Yak 的 `help install`、`search` 和 `list` 确认命令、可用包与已安装版本。优先复用已工作的包，不把接入任务扩大为自动升级 Rhino 或全部插件。

Windows PowerShell 示例，`$yak` 必须取自实际检测到的路径：

```powershell
& $yak help install
& $yak search Rhino-MCP-Platform
& $yak list
```

选择官方当前可用且兼容的版本，将实际版本号放入 `$packageVersion`，安装后检查退出码和列表：

```powershell
& $yak install --source=https://yak.rhino3d.com/ Rhino-MCP-Platform $packageVersion
if ($LASTEXITCODE -ne 0) { throw 'Rhino MCP installation failed; inspect the Yak error.' }
& $yak list
```

macOS 使用检测到的 Yak 可执行文件执行等价参数，不复制 PowerShell 的 `&`、变量和条件语法。安装到目标 Rhino 的用户包目录；具体路径以 Yak 输出为准。检查包版本、manifest、插件和对应架构 Router 文件。现有包目录或 Router 可运行不等于 Rhino 已加载插件；Rhino 已打开时按实际加载情况安排重启，不强制关闭用户未保存的文档。

**PackageManager 网络授权/联网失败：**先区分宿主沙箱、代理/证书、服务访问和 Rhino 许可问题。可在获准的网络环境下直接运行官方 Yak CLI；公开包搜索/下载不应一概当作必须登录 Rhino Account。网络被阻时使用宿主的权限入口，并明确需要访问的官方源与安装目录。未获得访问就不声称下载成功。

若 Rhino 所在环境不能联网，而另一个获准环境能取包，可从官方源获取兼容的 `.yak`，核对来源、分发版本及官方提供的校验信息，再传到目标环境本地安装：

```powershell
& $yak install $localYakPackage
```

不要猜测 CDN 文件名、改用同名第三方包或把 GitHub 源码仓库当作必有二进制 Releases。Yak 自 0.13.0 支持本地 `.yak` 路径；其他版本以其帮助为准。失败时保留具体错误，只有原因或条件变化才重试，不反复登录、重装或重写同一配置。

## 4. 连接用户实际使用的 AI 客户端

按需读 [客户端配置](rhino-mcp-clients.md)。支持本地 **stdio MCP** 的客户端可启动官方 `rhino-mcp-router`；如果使用 HTTP，必须核对 Rhino 实际服务地址和客户端支持的传输，不把普通网页聊天、SSE、Streamable HTTP 自动视为等价。

指导用户在 Rhino 运行 `MCPConnect`：

1. 自动检测到且有 Install 入口的客户端，可由用户点击安装连接配置，或在已授权范围内代为合并配置。`Not detected` 只说明未检测到，不能据此断言不支持。
2. 读取该版本对话框的 Prompt / mcp.json / Advanced 或相应页面，取得真实 Router 绝对路径、参数、目标 Rhino 版本。不要把示例 `rhino-mcp-router` 当成已加入 PATH。
3. 未在自动列表中的客户端，按它当前的官方 MCP 格式手动配置同一 Router。保留其他服务器、环境变量和用户选择；需要写配置时先备份已有文件并只合并 Rhino 条目。凭据留在客户端，日志及交付不输出密钥。
4. 按客户端要求保存、重启连接、重启客户端或新建会话，使工具被重新发现。检查实际工具列表；不要只凭配置文件存在宣称成功。

Rhino 与运行 stdio Router 的宿主需要能在同一本机环境访问；远程/云端聊天中的 localhost 不指向用户电脑。涉及跨主机接入时另行按官方可支持的传输设计，不为完成连接随意把 Rhino 服务暴露到公网。

## 5. 启动当前 Rhino 会话

MCPConnect 主要处理客户端配置。若会话列表仍为空，指导用户：

1. 关闭连接配置对话框，保持目标 Rhino 文档打开。
2. 在 Rhino 命令行运行 `MCPStart`；出现 Port 提示时按回车接受建议端口，或在冲突时选择空闲端口。
3. 等待命令历史显示本地服务地址，保持 Rhino 开启，返回 AI 客户端检查连接。支持 `MCPStatus` 的版本也可用它查看状态；不依赖所有版本都有此命令。

每次给用户当前所需的最少步骤，不一次要求填写全部配置或提供多张截图。能直接从工具读到状态时由 AI 自行检查。用户发“已启动”后立即列会话并读取指定文档，不再让用户重复安装或重启。

发现多个会话时用端口、文件名、版本、上下文匹配用户目标；不能唯一确定才询问。后续工具持续传入返回的真实 slot；不硬编码测试时的 slot、PID 或默认端口。只有用户要求新开模型窗口时才使用 spawn/new-instance 工具。

## 6. 建模与验收

连接检查默认只读。按用户已授权的建模任务及主 skill 的设计约定继续，不为了测试连接创建盒子或清空模型。

- 优先使用当前 MCP 暴露的 Rhino 原生几何、命令与 Python/C# 工具。脚本用该工具注入的 `__rhino_doc__` 作为目标文档；不依赖 `scriptcontext.doc`、`rhinoscriptsyntax` 的隐式文档或可能切换的 ActiveDoc。
- 确认单位、容差、楼层/坐标和对象 ID；已有项目按 UUID/图层/选择定位。保留原有对象，按操作使用撤销记录，长脚本及时返回结果。根据当前工具超时拆分适量操作，不因等待而重复提交同一建模脚本。
- 实体交付检查实际几何类型、`IsValid`、`IsSolid`，布尔结果个数及必要体积/尺寸。门窗洞口用墙体自身的交线/点内外或等价检查确认贯穿；网格、开口曲面不能冒充闭合 BRep。
- 结合模型数据和视口截图检查，截图工具按实际工具说明选择相机/框选范围，必要时以 Rhino 原生视口捕获保存预览。MCP 的图片可能嵌套在文本 JSON 内，先解析 content 再展示，避免把 base64 当正文输出。需要看图时仍受模型的图片输入能力约束。
- 保存可继续编辑的 `.3dm`，按本次需要保留脚本/参数；回读检查单位、关键对象、实体与洞口。工具成功或文件可解析不能替代实际设计和视觉验收。

交付明确当前已验证到哪一层：安装、客户端工具、指定 Rhino 文档、具体模型。未接通时给出剩余的具体用户操作或系统阻拦及来源；不把 Router 握手描述成已经在 Rhino 中建模。

## 官方入口

- [McNeel Rhino MCP Platform](https://mcneel.github.io/RhinoAI/) · [入门与客户端](https://mcneel.github.io/RhinoAI/docs/getting-started/) · [故障排查](https://mcneel.github.io/RhinoAI/docs/troubleshooting/)
- [Yak CLI：安装、包源与本地包](https://developer.rhino3d.com/guides/yak/yak-cli-reference/)
- [Rhino 的 .NET Core 运行时](https://developer.rhino3d.com/guides/rhinocommon/moving-to-dotnet-core/)
- [Rhino 命令说明：MCPConnect / MCPStart / MCPStatus](https://docs.mcneel.com/rhino/9/help/en-us/commands/mcpstatus.htm)（该页为 Rhino 9；Rhino 8 的实际命令以安装的插件为准）
