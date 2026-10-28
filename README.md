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

CZN Speed 是一个基于 LSPosed 的 Android 模块，为单机游戏 **Chaos Zero Nightmare** 提供运行时的游戏内变速与战斗动画跳过能力。

模块不修改游戏 APK，也不替换任何游戏资源。其工作方式是在目标进程加载后，将一段 JavaScript 注入游戏自身的 V8 上下文，由该脚本接管调度器的时间缩放与动画等待逻辑；注入完成后，native 侧不再干预游戏运行。

本项目基于 [yporoc/CZNSpeed-ZygiskNext](https://github.com/yporoc/CZNSpeed-ZygiskNext) 开发，沿用其 JS 运行时核心与 native 注入引擎，仅将装载方式由 Zygisk 模块迁移至 LSPosed。

> [!WARNING]
> 本模块是第三方软件，通过注入游戏进程修改运行时行为，**存在账号被处罚的可能**。

## 功能

- **变速**：默认 0x 至 20x 共 8 档预设（0、0.5、1、2、3、5、10、20），档位数量与数值均可自定义（2~8 档，上限 999）；0x 表示暂停。
- **动画跳过**：跳过战斗中的出牌、攻击与演出动画，缩短单回合耗时。
- **动画守卫**：在灵光一闪、Cut-in、必杀技等需要完整演出的流程中临时回到 1x，流程结束后自动恢复至设定倍速。
- **悬浮控制**：四态悬浮层 —— 收起球、展开胶囊、更多面板、档位编辑弹窗；仅收起态可拖动，编辑档位使用内置数字键盘。
- **配置持久化**：倍速、跳过开关与按钮位置保存至游戏可写目录，重启后自动恢复。

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

## 项目结构

```
app/src/main/
├── assets/xposed_init            # 模块入口类声明
├── java/com/czn/mod/Main.java    # IXposedHookLoadPackage 入口与 JNI 声明
├── res/values/arrays.xml         # 推荐作用域（xposed_scope）
├── AndroidManifest.xml           # 模块元信息
└── cpp/
    ├── czn_core.cpp              # native 注入引擎与 JNI 入口
    ├── CMakeLists.txt            # 编译配置与 JS 头生成
    ├── extract_js.py             # JS bundle 装配
    ├── gen_headers.py            # JS → C 头文件
    ├── 06_spark_guard.js         # 动画守卫（外部分节）
    └── 07_anim_skip.js           # 动画跳过（外部分节）
```

悬浮层界面、配置读写与调度器守卫等分节内嵌在 `extract_js.py` 中，编译前按固定顺序拼装为单个 bundle 注入游戏。

## 工作原理

1. LSPosed 在目标进程加载模块后调用 `Main.handleLoadPackage`，按包名与主进程过滤。
2. 通过 JNI 调用 `nativeStart`，在独立线程中启动注入流程。
3. 等待 `libssr.so`（游戏引擎库）被映射，并等待 V8 平台线程就绪。
4. 解析引擎 ELF 的动态符号表，定位 14 个 V8 API 符号。
5. 改写 `AAsset_read` 与 `AAssetManager_open` 的 GOT 槽作为注入触发点，确保在 JS 线程上取得有效的 `Isolate`。
6. 在 `HandleScope` / `TryCatch` 中编译并执行 JS bundle，完成后恢复 GOT，进入被动状态。

## 诊断

- 注入状态：`/storage/emulated/0/Android/data/<包名>/files/.czn_status`
- 运行日志：`adb logcat -s CZN`
- JS 侧环形日志与异常：游戏可写目录下的 `.czn_status`

状态文件内容包含注入阶段、失败原因（如 `FAIL: symbol missing`、`FAIL: no slots armed`）以及守卫异常释放记录，可用于定位引擎版本变更导致的问题。

## 已知限制

- V8 符号解析依赖引擎版本。游戏更新后若符号缺失，模块会保持惰性退出而不会影响游戏运行，需同步更新符号表。
- 仅提供 arm64-v8a 构建。
