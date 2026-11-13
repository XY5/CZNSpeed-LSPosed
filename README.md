<div align="center">

# CZN Speed

**Chaos Zero Nightmare 的游戏内变速与战斗动画跳过模块**

<br>

<div>
    <img alt="platform" src="https://img.shields.io/badge/platform-Android%208.1%20%7C%2014-blueviolet">
    <img alt="framework" src="https://img.shields.io/badge/framework-LSPosed-1f6feb">
    <img alt="arch" src="https://img.shields.io/badge/arch-arm64--v8a-555555">
</div>
<div>
    <img alt="license" src="https://img.shields.io/badge/license-GPL--3.0-3da639">
    <img alt="ndk" src="https://img.shields.io/badge/NDK-r26.1-ffa500">
</div>

</div>

## 简介

CZN Speed 是一个 LSPosed 模块，为单机游戏 **Chaos Zero Nightmare** 提供游戏内变速与战斗动画跳过。它不修改 APK、不替换资源，而是在目标进程加载后把一段 JavaScript 注入游戏自身的 V8 上下文，由脚本接管时间缩放与动画等待；注入完成后 native 侧只做轻量健康检查，不参与游戏逻辑。

基于 [yporoc/CZNSpeed-ZygiskNext](https://github.com/yporoc/CZNSpeed-ZygiskNext) 开发，沿用其 JS 运行时与 native 注入引擎，仅将装载方式由 Zygisk 迁移至 LSPosed。

> [!WARNING]
> 本模块是第三方软件，通过注入游戏进程修改运行时行为，**存在账号被处罚的可能**。

## 功能

- **变速**：默认 6 档（0、0.5、1、3、5、10），档位数量与数值可自定义（2~8 档，上限 999），0x 表示暂停。
- **动画跳过**：跳过战斗中的出牌、攻击与演出动画。
- **自动战斗解锁**：解除部分模式「无法使用自动战斗」的限制，更多面板可开关，**需在进入战斗前设置**。
- **动画守卫**：灵光一闪、Cut-in、必杀技等需要完整演出的流程临时回到 1x，结束后自动恢复。
- **悬浮控制**：收起球 / 展开胶囊 / 更多面板 / 档位编辑弹窗四态；仅收起态可拖动，档位用内置数字键盘编辑。
- **隐藏悬浮窗**：可完全隐藏；入口为更多面板或长按收起球，恢复靠左下角隐形热区（连点三次或长按）。隐藏不写配置、不改倍速。
- **配置持久化**：倍速、跳过开关与按钮位置存于游戏可写目录，重启自动恢复。

## 环境要求

- Android 8.1 ~ 14（LSPosed 官方支持范围；Android 15 及以上需使用社区维护的 LSPosed 分支）
- 已获取 root 权限（Magisk / KernelSU）
- 已安装 LSPosed（Zygisk 版本）
- 设备架构为 arm64-v8a

## 下载与安装

1. 从 [Releases](https://github.com/XY5/CZNSpeed-LSPosed/releases) 下载最新 APK 并安装。
2. 打开 LSPosed 管理器，在模块列表中启用 **CZN Speed**。
3. 在作用域中勾选目标游戏，推荐作用域已预置，直接勾选即可。
4. 强制停止游戏进程后重新启动。

模块状态可通过日志与状态文件确认，详见「诊断」一节。

## 构建

前置依赖：

- JDK 17 或更高
- Android SDK Platform 34、Build-Tools 34+
- Android NDK r26.1（`26.1.10909125`）
- CMake 3.22.1
- Python 3

构建命令：

```bash
./gradlew assembleDebug
```

产物位于 `app/build/outputs/apk/debug/app-debug.apk`。

> 修改过 JS 或 native 代码后建议使用 `./gradlew clean assembleDebug`，避免增量打包导致 APK 体积异常。

JS bundle 由 CMake 在编译前自动生成，无需手动干预；如需单独验证装配结果：

```bash
cd app/src/main/cpp && python extract_js.py && python gen_headers.py
```

## 排查

装好后没有任何反应，按顺序确认：

1. LSPosed 里模块已启用，作用域勾选了目标游戏；
2. 强制停止游戏进程后重新启动——模块在进程启动时装载，热重启无效；
3. 悬浮球是否出现。没有出现说明注入未成功。

仍然不行时抓日志反馈，文件在 `/storage/emulated/0/Android/data/<包名>/files/`：

- `.czn_log` —— 运行时日志，保留最近 120 行（启动、挂载、异常），反馈问题时带上这个；
- `.czn_status` —— 单行注入状态：`armed` / `stage1 ok` / `driver re-armed` / `FAIL: <原因>`；
- `.czn_dump` —— 仅在脚本抛异常时生成，含错误堆栈。

实时日志：`adb logcat -s CZN`。闪退时可在同目录新建 `czn_flags`（十六进制位掩码，缺省全开）逐项关闭功能定位，位含义见代码注释，不需要时删除即可。
