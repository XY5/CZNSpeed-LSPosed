// --- [MODULE START] 08_auto_battle.js ---
(function () {
// ============================================================
// 自动战斗解锁 —— 解除「部分模式不让用自动战斗」的限制
//
// 机制（引擎实测）：
//   · enable_auto_battle         只决定自动战斗按钮能不能点（9 行写死 NO）
//   · auto_battle_category_type  决定能否按类别记住并自动恢复；NONE 会让
//                                游戏跳过整条「记住/恢复」分支，所以只解锁
//                                按钮仍然每场都要手动点
//   两个都要改 ⇒ 按钮可用 + 进战斗自动开启，且状态继承游戏自身存档。
//
// 为什么 hook 而不是改资源文件：改 gameres 里的 db 会在游戏下次启动时被
// 按远端清单重下还原（实测有效但不可持续）。表解析在原生侧，JS 拿不到字节，
// 所以只能在行数据出口改写。
//
// yuna 的真实形态（实测，务必照此处理）：
//   · yuna 是函数对象，load_db / dbt_all / DBT / dbt_row 是它的自有属性
//     （w=true, c=true, e=false）⇒ 普通赋值即可 hook，回读 === 校验
//   · 绝不 defineProperty：往 Function.prototype 上 define 会直接黑屏，
//     try/catch 兜不住（进程级崩溃）
//   · 模块加载期 typeof yuna === 'undefined'，约 7s 后才出现 ⇒ 只能轮询等待，
//     由 __cznBootTick 每 0.5s 驱动，install 自带幂等
// ============================================================
'use strict';

var TARGET_TABLE = 'ingame_content_config';
var HOOKS = ['load_db', 'dbt_all', 'DBT', 'dbt_row'];
var FLAG = 0x2000;               // czn_flags: 关掉这一位即彻底停用本功能
var startedAt = Date.now();
var installed = false;
var staleLogged = false;
var patched = [];                // [{o, a, c}] 我们改过的行对象（持有引用以便回滚）

function _log(m) { try { globalThis._slog('[AB] ' + m); } catch (e) { } }
function _alog(m) { try { globalThis._alog('[AB] ' + m); } catch (e) { } }

function _on() { return globalThis._abOn !== false; }

function _yuna() {
    try { if (typeof yuna !== 'undefined' && yuna) return yuna; } catch (e) { }
    try { if (typeof window !== 'undefined' && window.yuna) return window.yuna; } catch (e) { }
    try { if (globalThis.yuna) return globalThis.yuna; } catch (e) { }
    return null;
}

// 首次见到某行时记下原始值；同一行只记一次
function _remember(o, a, c) {
    for (var i = 0; i < patched.length; i++) if (patched[i].o === o) return patched[i];
    var rec = { o: o, a: a, c: c };
    patched.push(rec);
    return rec;
}

// 单行改写。只碰带这两个字段的对象，其余一律不动。
// 开关关掉时把改过的行原样写回（我们持有的是游戏正在用的那个对象，
// 所以回滚即时生效，不需要重启游戏）。
function patchRow(o) {
    var ch = [];
    try {
        if (!o || typeof o !== 'object') return ch;
        var hasA = (o.enable_auto_battle === 'NO' || o.enable_auto_battle === 'YES');
        var hasC = (o.auto_battle_category_type !== undefined);
        if (!hasA && !hasC) return ch;
        var rec = _remember(o, o.enable_auto_battle, o.auto_battle_category_type);
        if (_on()) {
            if (o.enable_auto_battle === 'NO') {
                o.enable_auto_battle = 'YES';
                if (o.enable_auto_battle === 'YES') ch.push('auto:NO->YES');
            }
            // 只提升卡组构筑类；剧情类保持 NONE（它们的 NONE 是有意的，
            // 强开可能抢掉剧情节点）
            if (o.auto_battle_category_type === 'NONE' &&
                o.ingame_mode_type === 'INGAME_DECK_BUILDING') {
                o.auto_battle_category_type = 'CHAOS_AUTO';
                ch.push('cat:NONE->CHAOS_AUTO');
            }
        } else {
            if (rec.a !== undefined && o.enable_auto_battle !== rec.a) { o.enable_auto_battle = rec.a; ch.push('auto:revert'); }
            if (rec.c !== undefined && o.auto_battle_category_type !== rec.c) { o.auto_battle_category_type = rec.c; ch.push('cat:revert'); }
        }
    } catch (e) { }
    return ch;
}

// 返回值可能是单行、行数组或包了一层的对象
function patchTree(root, limit) {
    var rows = 0, tags = [], visited = 0;
    var guard = null, garr = null;
    try { guard = new Set(); } catch (e) { guard = null; garr = []; }
    var stack = [root];
    while (stack.length) {
        if (visited++ > limit) break;
        var o = stack.pop();
        if (!o || typeof o !== 'object') continue;
        if (guard) { if (guard.has(o)) continue; guard.add(o); }
        else { if (garr.indexOf(o) >= 0) continue; garr.push(o); }
        var c = patchRow(o);
        if (c.length) {
            rows++;
            for (var m = 0; m < c.length; m++) if (tags.indexOf(c[m]) < 0) tags.push(c[m]);
        }
        try {
            var ks = Object.keys(o);
            for (var i = 0; i < ks.length; i++) {
                var v = o[ks[i]];
                if (v && typeof v === 'object') stack.push(v);
            }
        } catch (e) { }
    }
    return { rows: rows, tags: tags };
}

// 普通赋值 + === 回读校验。绝不 defineProperty。
function wrap(y, name) {
    var orig;
    try { orig = y[name]; } catch (e) { return false; }
    if (typeof orig !== 'function') return false;
    if (orig.__abWrapped) {
        // 已经是我们包的。若来自另一个 V8 context，说明引擎重建过 context 而
        // yuna 这个对象还活着 —— 再包一层就会把游戏调用导进已销毁的 context
        // （段错误，JS 层拦不住）。此时宁可让功能失效，也不碰它。
        if (orig.__abCtx !== globalThis.__cznCtxId) {
            if (!staleLogged) {
                staleLogged = true;
                _alog('yuna.' + name + ' 带着旧 context(' + orig.__abCtx + ') 的包装，跳过');
            }
            return true;
        }
        return true;
    }
    var wrapped = function () {
        var res = orig.apply(this, arguments);
        try {
            var a0 = arguments.length ? String(arguments[0]) : '';
            if (a0.indexOf(TARGET_TABLE) >= 0) {
                var r = patchTree(res, 200000);
                if (r.rows > 0) {
                    _alog('解锁 ' + (arguments.length > 1 ? String(arguments[1]) : a0) +
                        '：' + r.tags.join('，'));
                }
            }
        } catch (e) { _log(name + ' 异常: ' + e); }
        return res;
    };
    wrapped.__abWrapped = true;
    wrapped.__abCtx = globalThis.__cznCtxId;
    try { y[name] = wrapped; } catch (e) { _log('覆盖 yuna.' + name + ' 失败: ' + e); return false; }
    var ok = false;
    try { ok = (y[name] === wrapped); } catch (e) { }
    if (!ok) { _log('覆盖 yuna.' + name + ' 后回读不一致，放弃'); return false; }
    return true;
}

// 幂等安装入口，由 __cznBootTick 每 tick 调用一次
globalThis._tryInstallAutoBattle = function () {
    try {
        if (installed) return true;
        if (!globalThis._fl(FLAG)) return true;                 // 被 czn_flags 关掉
        if (!_on() && patched.length === 0) return true;         // 关着且没改过任何行：不必装
        if (Date.now() - startedAt < 1500) return true;          // 别在引擎刚起来时碰 yuna
        var y = _yuna();
        if (!y) return true;                                     // 还没出现，下次 tick 再试
        var got = [];
        for (var i = 0; i < HOOKS.length; i++) if (wrap(y, HOOKS[i])) got.push(HOOKS[i]);
        if (got.length) {
            installed = true;
            _alog('已挂钩 yuna: ' + got.join('+') + ' ctx=' + globalThis.__cznCtxId);
        }
    } catch (e) { _log('install 异常: ' + e); }
    return true;
};

// 面板开关：写盘 + 就地回写所有已改过的行
globalThis._toggleAutoBattle = function () {
    globalThis._abOn = !_on();
    try { globalThis._saveSpeedConfig(); } catch (e) { }
    var n = 0;
    for (var i = 0; i < patched.length; i++) {
        try { if (patchRow(patched[i].o).length) n++; } catch (e) { }
    }
    _alog('开关=' + (_on() ? 'on' : 'off') + '，就地回写 ' + n + ' 行');
    return _on();
};

_log('模块加载 ctx=' + globalThis.__cznCtxId + ' typeof yuna=' +
    (function () { try { return typeof yuna; } catch (e) { return 'ERR'; } })());
})();
// --- [MODULE END] 08_auto_battle.js ---
