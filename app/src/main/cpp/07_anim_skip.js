// --- [MODULE START] 07_anim_skip.js ---
(function() {
// ============================================================
// F11 触发 — 战斗动画跳过 v2
// 策略：Hook cc.DelayTime.create + 扫描实体 action_state
// 只在战斗中生效，不影响 UI / 大厅
// ============================================================
globalThis._animSkipEnabled = false;
var _animSkipTimer = null;
var _skipStats = { delayHooked: 0, delaySkipped: 0, entityForced: 0, spineAccel: 0 };
var _timerHookLog = 0; // 定时器 hook 日志计数

// (comprehensiveProbe, probeBattleGlobals, inBattle — deleted: pure probing code)
// ---- Hook 1: cc.DelayTime.create ----
var _origDelayTimeCreate = null;

function _hookDelayTime() {
    if (_origDelayTimeCreate) return; // 已经 hook 过
    try {
        if (cc && cc.DelayTime && cc.DelayTime.create) {
            _origDelayTimeCreate = cc.DelayTime.create;
            cc.DelayTime.create = function (duration) {
                _skipStats.delayHooked++;
                if (globalThis._animSkipEnabled && !_sparkGuardActive && duration > 0.02) {
                    _skipStats.delaySkipped++;
                    return _origDelayTimeCreate.call(this, 0.001);
                }
                return _origDelayTimeCreate.call(this, duration);
            };
            globalThis._speedLog('[SKIP] Hooked cc.DelayTime.create');
        } else {
            globalThis._speedLog('[SKIP] cc.DelayTime.create not found');
        }
    } catch (e) {
        globalThis._speedLog('[SKIP] DelayTime hook err: ' + e);
    }
}

// ---- Hook 2: cc.FadeIn / cc.FadeOut / cc.ScaleTo 等动画 ----
var _origFadeInCreate = null;
var _origFadeOutCreate = null;

function _hookFadeAnimations() {
    try {
        if (cc.FadeIn && cc.FadeIn.create && !_origFadeInCreate) {
            _origFadeInCreate = cc.FadeIn.create;
            cc.FadeIn.create = function (duration) {
                if (globalThis._animSkipEnabled && duration > 0.02) {
                    return _origFadeInCreate.call(this, 0.001);
                }
                return _origFadeInCreate.call(this, duration);
            };
        }
        if (cc.FadeOut && cc.FadeOut.create && !_origFadeOutCreate) {
            _origFadeOutCreate = cc.FadeOut.create;
            cc.FadeOut.create = function (duration) {
                if (globalThis._animSkipEnabled && duration > 0.02) {
                    return _origFadeOutCreate.call(this, 0.001);
                }
                return _origFadeOutCreate.call(this, duration);
            };
        }
        globalThis._speedLog('[SKIP] Hooked FadeIn/FadeOut.create');
    } catch (e) {
        globalThis._speedLog('[SKIP] Fade hook err: ' + e);
    }
}

// ---- Hook 3: 实体 Spine 加速 ----
var _entityProbed = false;

var _cachedInterceptEntity = null; // getEntityOfUID 拦截到的实体临时缓存

function _collectEntities() {
    var list = [];
    try {
        var em = globalThis['EntityManager'];
        if (!em) return list;

        // 诊断：列出 EntityManager 的所有属性（包括原型链）
        var allProps = [];
        var propCount = 0;
        for (var k in em) {
            propCount++;
            if (propCount <= 30) {
                allProps.push(k + '=' + typeof em[k]);
            }
        }
        if (!_entityProbed) {
            globalThis._speedLog('[EM] All props(' + propCount + '): ' + allProps.join(', '));
        }

        // 方案1: 直接属性名
        var searchKeys = ['team', 'monsters', 'supporter_team', '_team', '_monsters',
            'entities', '_entities', 'entityList', 'list', 'characters',
            'actors', '_actors', 'members', 'units'];
        for (var s = 0; s < searchKeys.length; s++) {
            var val = em[searchKeys[s]];
            if (val) {
                if (Array.isArray(val)) {
                    for (var i = 0; i < val.length; i++) if (val[i]) list.push(val[i]);
                } else if (typeof val === 'object') {
                    var vk = Object.keys(val);
                    for (var i = 0; i < vk.length; i++) if (val[vk[i]] && typeof val[vk[i]] === 'object') list.push(val[vk[i]]);
                }
                if (list.length > 0 && !_entityProbed) {
                    globalThis._speedLog('[EM] Found ' + list.length + ' entities via em.' + searchKeys[s]);
                    break;
                }
            }
        }

        // 方案2: 遍历所有属性，找包含 playAnimation 或 showSparkEffect 方法的对象
        if (list.length === 0) {
            for (var k in em) {
                try {
                    var v = em[k];
                    if (v && typeof v === 'object' && !Array.isArray(v)) {
                        // 是不是实体对象？
                        if (typeof v.playAnimation === 'function' || typeof v.showSparkEffect === 'function') {
                            list.push(v);
                            if (!_entityProbed) globalThis._speedLog('[EM] Found entity at em.' + k);
                        }
                        // 是不是容器（Map/数组）包含实体？
                        if (list.length === 0) {
                            for (var kk in v) {
                                try {
                                    var vv = v[kk];
                                    if (vv && typeof vv === 'object' &&
                                        (typeof vv.playAnimation === 'function' || typeof vv.showSparkEffect === 'function')) {
                                        list.push(vv);
                                        if (!_entityProbed) globalThis._speedLog('[EM] Found entity at em.' + k + '.' + kk);
                                    }
                                } catch (e2) { }
                                if (list.length >= 3) break;
                            }
                        }
                    }
                } catch (e) { }
                if (list.length >= 3) break;
            }
        }

        // 方案3: Hook getEntityOfUID 来拦截实体引用
        // v15: 增加 Error().stack 检测 selectCardRSpark 调用链
        if (list.length === 0 && typeof em.getEntityOfUID === 'function' && !em._origGetEntityOfUID) {
            em._origGetEntityOfUID = em.getEntityOfUID;
            em.getEntityOfUID = function (uid) {
                var entity = em._origGetEntityOfUID.call(this, uid);
                if (entity && !_protoHooked) {
                    globalThis._speedLog('[EM-INTERCEPT] Got entity from getEntityOfUID(uid=' + uid + '), hooking prototype...');
                    _cachedInterceptEntity = entity;
                    try { _hookEntityPlayAnimation(true); } catch (e) { }
                    _cachedInterceptEntity = null;
                }
                // v15: Stack trace R-Spark detection
                // getEntityOfUID 是唯一不被 V8 IC 绕过的 hook 点
                // selectCardRSpark 在选牌时调用 EntityManager.getEntityOfUID(char_id)
                // 检查调用栈来判断当前是否处于 R-Spark 流程
                // 守卫期间不必再采样（已经在 1x 了），省掉每次调用的 stack 开销
                if (!globalThis._sparkGuardActive) {
                    _getEntityCallCount++;
                    try {
                        var stack = new Error().stack;
                        // 诊断: 前10次调用记录 stack 前150字符
                        if (globalThis._animSkipEnabled && _getEntityCallCount <= 10) {
                            globalThis._speedLog('[EM-CALL#' + _getEntityCallCount + '] uid=' + uid + ' stack=' + (stack ? stack.substring(0, 150).replace(/\n/g, ' | ') : 'N/A'));
                        }
                        if (stack && (stack.indexOf('selectCardRSpark') >= 0 || stack.indexOf('selectCardSpark') >= 0)) {
                            globalThis._speedLog('[SPARK] >>> R-SPARK GUARD ON via M5:stack-trace (uid=' + uid + ')');
                            globalThis._speedLog('[SPARK] stack: ' + stack.substring(0, 300));
                            globalThis._guardOn(15000, 'stack-rspark');
                        }
                    } catch (e) { }
                }
                return entity;
            };
            globalThis._speedLog('[EM] Hooked getEntityOfUID as entity interceptor (v15: +stack-trace R-Spark detection)');
        }

    } catch (e) {
        globalThis._speedLog('[EM] collectEntities error: ' + e);
    }
    return list;
}



// ---- 方案 v12: PROTOTYPE-LEVEL hook ----
// v10/v11 失败原因: V8 Inline Cache (IC) 缓存了属性查找结果
//   编译后的字节码 GetNamedProperty 第一次执行时缓存了函数引用
//   之后的调用直接用缓存，不再经过 JS 属性查找
//   因此实例级别的属性覆盖被 IC 完全绕过
// v12: hook PROTOTYPE 上的方法 — IC 缓存的是 prototype slot 的引用
//   修改 prototype 上的函数 → 所有调用都被拦截
var _protoHooked = false;
var _origProtoPlayAnimation = null;
var _origProtoSetAnimation = null;
var _origProtoGetAnimLen = null;
var _playAnimLogCount = 0;
var _MAX_PLAY_LOGS = 200;
// 守卫只剩两条"选牌"触发点：06 的选牌弹窗 hook，
// 以及本文件 getEntityOfUID 里的 selectCardRSpark 栈检测。
var _getEntityCallCount = 0;  // v15: getEntityOfUID 调用计数

// 现在只剩两条"选牌"守卫：
//   1) 06 的 RSparkManager.createRSparkSelectPopup —— 选牌弹窗打开时 3s
//   2) 本文件 getEntityOfUID 的 selectCardRSpark 调用栈 —— 选牌动作 15s
// buff / debuff / 崩坏 / cut-in / 必杀 / lead / 崩溃 / spark 特效的触发点
// 全部移除：它们各自依赖未经验证的事件名和方法名，误触发一次就是整段战斗
// 被压回 1x，而收益只有"看清动画"。等真机日志确认了事件名再逐个加回来。



// 守卫 hook 必须常驻，与"跳过动画"开关无关。
// 旧实现只在 _toggleCardSkip 的 ON 分支里装原型 hook，于是 skip=0 的玩家
// 连一个守卫触发点都没有，选牌流程被 05 的 reconcile 直接拉回用户速度。
function _installGuardHooks() {
    if (globalThis._fl && !globalThis._fl(0x800)) return false;  // 原型 hook 可被 flags 关掉
    // 06 的选牌弹窗守卫与跳过开关无关，一并保活
    try { if (typeof globalThis._ensureGuardsInstalled === 'function') globalThis._ensureGuardsInstalled(); } catch (e) { }
    if (!_protoHooked) { try { _hookEntityPlayAnimation(true); } catch (e) { } }
    return _protoHooked;
}


function _hookEntityPlayAnimation(enable) {
    var entities = _collectEntities();
    // getEntityOfUID 拦截器缓存的实体（_collectEntities 搜不到时的后备）
    if (entities.length === 0 && _cachedInterceptEntity) {
        entities = [_cachedInterceptEntity];
    }

    if (enable) {
        var hookCount = 0;

        // === 策略 1: Prototype-level hook ===
        // 找到 playAnimation 定义在原型链的哪一层，直接修改那个 prototype
        if (!_protoHooked && entities.length > 0) {
            var ent = entities[0];

            // --- 探测 entity 原型链 ---
            try {
                var proto = Object.getPrototypeOf(ent);
                var depth = 0;
                var protoChainLog = [];
                while (proto && depth < 10) {
                    var ownKeys = [];
                    try { ownKeys = Object.getOwnPropertyNames(proto); } catch (e) { }
                    var hasPlayAnim = ownKeys.indexOf('playAnimation') >= 0;
                    var constructorName = '';
                    try { constructorName = proto.constructor ? proto.constructor.name : ''; } catch (e) { }
                    protoChainLog.push('L' + depth + ':' + constructorName +
                        '(keys=' + ownKeys.length +
                        ',playAnim=' + hasPlayAnim + ')');

                    if (hasPlayAnim && typeof proto.playAnimation === 'function' && !_origProtoPlayAnimation) {
                        _origProtoPlayAnimation = proto.playAnimation;
                        proto.playAnimation = function (animName, loop) {
                            if (_playAnimLogCount < _MAX_PLAY_LOGS) {
                                _playAnimLogCount++;
                                var label = '';
                                try { label = this.getName ? this.getName() : ''; } catch (e) { }
                                globalThis._speedLog('[PLAY-P] ' + label +
                                    ' "' + animName + '"' +
                                    ' loop=' + loop +
                                    ' skip=' + (globalThis._animSkipEnabled && !_sparkGuardActive && !loop));
                            }

                            if (globalThis._animSkipEnabled && !_sparkGuardActive && !loop) {
                                _origProtoPlayAnimation.call(this, animName, loop);
                                return 0.001;
                            }
                            return _origProtoPlayAnimation.call(this, animName, loop);
                        };
                        hookCount++;
                        globalThis._speedLog('[PROTO] Hooked playAnimation on prototype L' + depth + ':' + constructorName);
                    }


                    proto = Object.getPrototypeOf(proto);
                    depth++;
                }
                globalThis._speedLog('[PROTO] entity chain: ' + protoChainLog.join(' → '));
            } catch (e) {
                globalThis._speedLog('[PROTO] entity chain error: ' + e);
            }

            // --- 探测 aninode 原型链 (setAnimation + getAnimationLength) ---
            try {
                var an = entities[0].aninode;
                if (an) {
                    var proto = Object.getPrototypeOf(an);
                    var depth = 0;
                    var aniProtoLog = [];
                    while (proto && depth < 10) {
                        var ownKeys = [];
                        try { ownKeys = Object.getOwnPropertyNames(proto); } catch (e) { }
                        var hasSetAnim = ownKeys.indexOf('setAnimation') >= 0;
                        var hasGetLen = ownKeys.indexOf('getAnimationLength') >= 0;
                        var constructorName = '';
                        try { constructorName = proto.constructor ? proto.constructor.name : ''; } catch (e) { }
                        aniProtoLog.push('L' + depth + ':' + constructorName +
                            '(setAnim=' + hasSetAnim +
                            ',getLen=' + hasGetLen + ')');

                        // Hook setAnimation on prototype
                        if (hasSetAnim && typeof proto.setAnimation === 'function' && !_origProtoSetAnimation) {
                            _origProtoSetAnimation = proto.setAnimation;
                            proto.setAnimation = function (track, animName, loop) {
                                if (_playAnimLogCount < _MAX_PLAY_LOGS) {
                                    _playAnimLogCount++;
                                    var label = '';
                                    try { label = this.getName ? this.getName() : ''; } catch (e) { }
                                    globalThis._speedLog('[ANIM-P] ' + label +
                                        ' "' + animName + '"' +
                                        ' loop=' + loop);
                                }
                                var result = _origProtoSetAnimation.call(this, track, animName, loop);
                                // 不吞掉动画，只记录触发
                                return result;
                            };
                            hookCount++;
                            globalThis._speedLog('[PROTO] Hooked setAnimation on aninode prototype L' + depth);
                        }

                        // Hook getAnimationLength on prototype
                        if (hasGetLen && typeof proto.getAnimationLength === 'function' && !_origProtoGetAnimLen) {
                            _origProtoGetAnimLen = proto.getAnimationLength;
                            proto.getAnimationLength = function (animName) {
                                var orig = _origProtoGetAnimLen.call(this, animName);
                                if (globalThis._animSkipEnabled) {
                                    if (_playAnimLogCount < _MAX_PLAY_LOGS) {
                                        _playAnimLogCount++;
                                        globalThis._speedLog('[LEN-P] "' + animName + '" orig=' + orig + ' → 0.001');
                                    }
                                    return 0.001;
                                }
                                return orig;
                            };
                            hookCount++;
                            globalThis._speedLog('[PROTO] Hooked getAnimationLength on aninode prototype L' + depth);
                        }

                        proto = Object.getPrototypeOf(proto);
                        depth++;
                    }
                    globalThis._speedLog('[PROTO] aninode chain: ' + aniProtoLog.join(' → '));
                }
            } catch (e) {
                globalThis._speedLog('[PROTO] aninode chain error: ' + e);
            }

            _protoHooked = true;
        }

        if (_timerHookLog < 10 && hookCount > 0) {
            _timerHookLog++;
            globalThis._speedLog('[TIMER] v12 hooked ' + hookCount + ' prototype methods');
        }

        return hookCount;
    }
}

// ---- Hook 4: timeSleep / waitForNextFrame — 战斗核心等待 ----
// framework.js 把这些挂到 globalThis 上：
//   timeSleep(ms)          → Promise, resolve after ms (Date.now based)
//   waitForNextFrame()     → Promise, resolve next frame
//   waitForNextFrames(n)   → Promise, resolve after n frames
// 战斗协程用 await timeSleep(ms) 等待动画完成
var _origTimeSleep = null;
var _origWaitForNextFrame = null;
var _origWaitForNextFrames = null;
var _tsHookCount = 0;
var _tsSkipCount = 0;

function _hookTimeSleep() {
    // Hook timeSleep — 这是战斗中最关键的等待
    try {
        var ts = globalThis['timeSleep'];
        if (ts && typeof ts === 'function' && !_origTimeSleep) {
            _origTimeSleep = ts;
            globalThis['timeSleep'] = function (ms) {
                _tsHookCount++;
                if (globalThis._animSkipEnabled && !_sparkGuardActive) {
                    _tsSkipCount++;
                    return _origTimeSleep(1);
                }
                return _origTimeSleep(ms);
            };
            globalThis._speedLog('[SKIP] Hooked globalThis.timeSleep');
        } else {
            globalThis._speedLog('[SKIP] timeSleep not found on globalThis, type=' + typeof ts);
        }
    } catch (e) {
        globalThis._speedLog('[SKIP] timeSleep hook err: ' + e);
    }

    // Hook waitForNextFrame — 用 setTimeout(1ms) 代替等下一帧
    // 之前担心死循环，但 setTimeout 会 yield 到事件循环，不会阻塞
    // 原始等待 ~16ms/帧，现在 ~1ms → 轮询循环快 16 倍
    try {
        var wnf = globalThis['waitForNextFrame'];
        if (wnf && typeof wnf === 'function' && !_origWaitForNextFrame) {
            _origWaitForNextFrame = wnf;
            globalThis['waitForNextFrame'] = function () {
                if (globalThis._animSkipEnabled && !_sparkGuardActive) {
                    return new Promise(function (resolve) {
                        setTimeout(resolve, 0);
                    });
                }
                return _origWaitForNextFrame();
            };
            globalThis._speedLog('[SKIP] Hooked waitForNextFrame → setTimeout(0)');
        } else {
            globalThis._speedLog('[SKIP] waitForNextFrame: type=' + typeof wnf);
        }
    } catch (e) {
        globalThis._speedLog('[SKIP] waitForNextFrame hook err: ' + e);
    }

    // Hook waitForNextFrames 同理
    try {
        var wnfs = globalThis['waitForNextFrames'];
        if (wnfs && typeof wnfs === 'function' && !_origWaitForNextFrames) {
            _origWaitForNextFrames = wnfs;
            globalThis['waitForNextFrames'] = function (n) {
                if (globalThis._animSkipEnabled && !_sparkGuardActive) {
                    return new Promise(function (resolve) {
                        setTimeout(resolve, 0);
                    });
                }
                return _origWaitForNextFrames(n);
            };
            globalThis._speedLog('[SKIP] Hooked waitForNextFrames → setTimeout(0)');
        }
    } catch (e) { }

    // 也探测 SimpleWait（之前的目标）
    try {
        var sw = globalThis['SimpleWait'];
        if (sw && typeof sw === 'function') {
            var origSW = sw;
            globalThis['SimpleWait'] = function (ms) {
                if (globalThis._animSkipEnabled && !_sparkGuardActive && ms > 16) {
                    return origSW(1);
                }
                return origSW(ms);
            };
            globalThis._speedLog('[SKIP] Hooked globalThis.SimpleWait');
        }
    } catch (e) { }
}

// ---- 主切换函数 ----
// v8: 跳过动画 — setAnimation hook
//   1. timeSleep hook → 缩短逻辑等待
//   2. setAnimation hook → 动画开始后立刻跳到结束
//   3. DelayTime hook → 完成回调 0.001s 触发
//   → 整个出牌/攻击流程秒完成
var _entityTimer = null;

function _toggleCardSkip() {
    globalThis._animSkipEnabled = !globalThis._animSkipEnabled;

    if (globalThis._animSkipEnabled) {
        globalThis._speedLog('=== ANIMATION SKIP v17: ON (select-card guard only) ===');
        _getEntityCallCount = 0;

        _hookDelayTime();
        _hookFadeAnimations();
        _hookTimeSleep();

        // 选牌守卫的两条触发点：06 的选牌弹窗 hook + 本文件的 selectCardRSpark 栈检测
        try { _installComprehensiveSparkGuard(); } catch (e) { }
        try { _installSparkGuard(); } catch (e) { }
        try { _installGuardHooks(); } catch (e) { }


        // Hook 战斗实体的 playAnimation + getAnimationLength (v11)
        var hookCount = _hookEntityPlayAnimation(true);
        globalThis._speedLog('[SKIP] Hooked playAnimation+getAnimLen on ' + hookCount + ' targets');


        // 定时器持续 hook 新实体
        if (_entityTimer) clearInterval(_entityTimer);
        _entityTimer = setInterval(function () {
            if (!globalThis._animSkipEnabled) return;
            _hookEntityPlayAnimation(true);
        }, 500);

    } else {
        globalThis._speedLog('=== ANIMATION SKIP v17: OFF ===');
        globalThis._speedLog('[SKIP] Stats: delayHook=' + _skipStats.delayHooked +
            ' delaySkip=' + _skipStats.delaySkipped +
            ' tsHook=' + _tsHookCount +
            ' tsSkip=' + _tsSkipCount +
            ' entityCalls=' + _getEntityCallCount);

        // 停止定时器
        if (_entityTimer) {
            clearInterval(_entityTimer);
            _entityTimer = null;
        }

        // 不再卸载原型 hook：守卫（灵光一闪 / cut-in / 必杀）依赖它们常驻，
        // 而"是否跳过"完全由 wrapper 里的 _animSkipEnabled 判断控制 ——
        // 关掉开关后这些 wrapper 只是原样透传，没有任何副作用。
        globalThis._guardOff('toggle-off');
    }

    _updateSpeedLabel();
}



    var AnimSkipService = {
        _toggleCardSkip: _toggleCardSkip,
        _hookDelayTime: _hookDelayTime,
        _hookFadeAnimations: _hookFadeAnimations,
        _hookTimeSleep: _hookTimeSleep,
        installGuardHooks: _installGuardHooks,
    };
    __app.registerService('AnimSkipService', AnimSkipService);
    globalThis._installGuardHooks = _installGuardHooks;
    globalThis._toggleCardSkip = _toggleCardSkip;
    globalThis._hookDelayTime = _hookDelayTime;
    globalThis._hookFadeAnimations = _hookFadeAnimations;
    globalThis._hookTimeSleep = _hookTimeSleep;
})();
// --- [MODULE END] 07_anim_skip.js ---

// --- End of 07_anim_skip.js ---
