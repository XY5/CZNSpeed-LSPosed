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

1. LSPosed 调用 `Main.handleLoadPackage`，按包名与主进程过滤。
2. 通过 JNI 进入 `nativeStart`，在独立线程执行注入，不阻塞游戏启动。
3. 等 `libssr.so` 映射、V8 平台线程就绪，解析 ELF 动态符号表定位 14 个 V8 API；任一缺失即惰性退出。
4. 改写 `AAsset_read` 与 `AAssetManager_open` 的 GOT 槽作为触发点——资源读取恰好发生在 JS 线程上，且只在当前线程持有 V8 context 时注入。
5. 在自建的 `HandleScope` 内执行 JS bundle。脚本不把回调托管给引擎的长生命周期对象（调度器、定时器、全局监听），因此切场景或重建 V8 上下文不会留下悬空回调。
6. 之后 GOT 槽保持挂载但完全透传，只做健康检查：层与驱动都在则不动，层丢失则重注入，驱动丢失则重新挂载。检查只在资源读取时发生，不参与逐帧逻辑。

## 诊断

文件均在 `/storage/emulated/0/Android/data/<包名>/files/`：

- `.czn_status` —— native 单行注入状态：`armed` / `stage1 ok` / `driver re-armed` / `FAIL: <原因>`。
- `.czn_log` —— JS 层追加日志，保留最近 120 行（启动、挂载、驱动重挂、异常），体积有界。
- `.czn_dump` —— 仅在 bundle 抛异常时生成，含错误堆栈与环形日志。

实时日志：`adb logcat -s CZN`。排查闪退可在同目录写 `czn_flags`（十六进制位掩码，缺省全开）逐项关闭功能定位，详见代码注释；不需要时删除即可。

## 已知限制

- V8 符号依赖引擎版本：游戏更新后符号缺失会惰性退出（不影响游戏运行），需同步更新符号表。
- 仅提供 arm64-v8a 构建。
