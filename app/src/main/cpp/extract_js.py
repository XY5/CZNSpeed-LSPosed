# czn-speed JS bundle assembler.
# Sections 06/07 are read from this folder (toolkit-derived);
# the rest are original sources below. Output: mod_js.js.
import io, os, re

here = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(here, "mod_js.js")

src = io.open(os.path.join(here, "06_spark_guard.js"), encoding="utf-8").read()
lines = src.split("\n")
marks = []
for i, ln in enumerate(lines):
    if ln.startswith("// --- Start of "):
        marks.append((i, ln.split("Start of ")[1].split(" ---")[0]))
marks.append((len(lines), "EOF"))
sec = {}
for k in range(len(marks) - 1):
    sec[marks[k][1]] = "\n".join(lines[marks[k][0] + 1:marks[k + 1][0]]).rstrip() + "\n"

# ================================================================ 00_timers
SEC00 = r"""// --- [MODULE START] 00_timers ---
(function() {
    try {
        if (globalThis._timersHooked) return;
        var origSetTimeout = globalThis.setTimeout;
        var origSetInterval = globalThis.setInterval;
        if (typeof origSetTimeout !== 'function') return;
        function _spd() {
            var v = globalThis._curSpeed;
            return (typeof v === 'number' && v > 0) ? v : ((v === 0) ? 0 : 1);
        }
        function _tmo(t, s) {
            if (!(t > 0)) return t;
            if (s === 0) return 2147483647;          // 0x: V8 timers pause too
            return Math.max(0, Math.round(t / s));
        }
        globalThis.setTimeout = function (handler, timeout) {
            var s = _spd();
            var t = (typeof timeout === 'number') ? _tmo(timeout, s) : timeout;
            var a = []; for (var i = 2; i < arguments.length; i++) a.push(arguments[i]);
            if (a.length > 0) return origSetTimeout.call(this, handler, t, a[0], a[1], a[2], a[3]);
            return origSetTimeout.call(this, handler, t);
        };
        globalThis.setInterval = function (handler, timeout) {
            var s = _spd();
            var t = (typeof timeout === 'number') ? _tmo(timeout, s) : timeout;
            var a = []; for (var i = 2; i < arguments.length; i++) a.push(arguments[i]);
            if (a.length > 0) return origSetInterval.call(this, handler, t, a[0], a[1], a[2], a[3]);
            return origSetInterval.call(this, handler, t);
        };
        globalThis._timersHooked = true;
    } catch (e) { }
})();
// --- [MODULE END] 00_timers ---
"""
sec["00_timers.js"] = SEC00

# ================================================================ 03_framework
SEC03 = r"""// --- [MODULE START] 03_framework ---
globalThis.__app = {
    services: {},
    registerService: function (name, service) {
        this.services[name] = service;
        try { if (typeof globalThis._slog === 'function') globalThis._slog('[App] ' + name); } catch (e) { }
    },
    getService: function (name) { return this.services[name] || null; }
};
// --- [MODULE END] 03_framework ---
"""
sec["03_framework.js"] = SEC03

# ================================================================ 04_config
SEC04 = r"""// --- [MODULE START] 04_config ---
(function() {
    var _ring = [], _ringMax = 80;
    globalThis._slog = function (msg) {
        try { _ring.push(String(msg)); if (_ring.length > _ringMax) _ring.shift(); } catch (e) { }
    };
    globalThis._slogDump = function () { return _ring.join('\n'); };

    // Idempotent defaults: a re-inject (V8 context rebuild on a scene swap)
    // re-runs this whole bundle into a fresh globalThis. If the config already
    // survived a same-context re-eval we must NOT clobber it; only seed when
    // the value is absent.
    if (globalThis._curSpeed === undefined) globalThis._curSpeed = 1;          // applied speed (float, single source of truth)
    if (globalThis._skipOnBoot === undefined) globalThis._skipOnBoot = false;
    if (globalThis._btnPosX === undefined) globalThis._btnPosX = 60;
    if (globalThis._btnPosY === undefined) globalThis._btnPosY = 100;
    if (globalThis._speedsList === undefined) globalThis._speedsList = [0, 0.5, 1, 3, 5, 10];   // editable speed levels

    var FU = function () { try { return cc.FileUtils.getInstance(); } catch (e) { return null; } };
    var _path = function () { var f = FU(); return ((f && f.getWritablePath) ? f.getWritablePath() : '') + 'cfg.dat'; };

    // Runtime feature mask, read from <files>/czn_flags as hex (e.g. "1f3").
    // Absent file = everything on. Native side reads the same file for its own
    // bits. Kept in the shipped build: it is the fastest way to bisect a crash
    // report on a user device without a rebuild.
    //   0x100 overlay UI   0x200 tick driver   0x400 timeScale guard
    //   0x800 prototype hooks (spark guard)    0x1000 touch listener
    globalThis._flags = 0xFFFFFFFF;
    try {
        var _ff = FU();
        if (_ff && _ff.isFileExist(_ff.getWritablePath() + 'czn_flags')) {
            var _raw = String(_ff.getStringFromFile(_ff.getWritablePath() + 'czn_flags') || '');
            _raw = _raw.replace(/[^0-9a-fA-FxX]/g, '');
            var _fv = parseInt(_raw, 16);
            if (!isNaN(_fv)) globalThis._flags = _fv;
        }
    } catch (e) { }
    globalThis._fl = function (bit) { return (globalThis._flags & bit) !== 0; };

    globalThis._loadSpeedConfig = function () {
        try {
            var f = FU(); if (!f) return;
            if (!f.isFileExist(_path())) return;
            var content = f.getStringFromFile(_path());
            if (!content || content.length < 3) return;
            var lines = content.split('\n');
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i].trim(); if (!line || line.charAt(0) === '#') continue;
                var eq = line.indexOf('='); if (eq < 0) continue;
                var k = line.substring(0, eq).trim().toLowerCase();
                var v = line.substring(eq + 1).trim();
                if (k === 'speed') { var s = parseFloat(v); if (!isNaN(s) && s >= 0 && isFinite(s)) globalThis._curSpeed = Math.round(s * 100) / 100; }
                else if (k === 'skip') { globalThis._skipOnBoot = (v === '1'); }
                else if (k === 'btn_x') { var x = parseInt(v, 10); if (!isNaN(x)) globalThis._btnPosX = x; }
                else if (k === 'btn_y') { var y = parseInt(v, 10); if (!isNaN(y)) globalThis._btnPosY = y; }
                else if (k === 'speeds') { var L = globalThis._parseLevels(v); if (L && L.length >= 2) globalThis._speedsList = L; }
            }
        } catch (e) { }
    };
    globalThis._saveSpeedConfig = function () {
        try {
            var f = FU(); if (!f) return;
            var txt = ['# czn mod',
                       'speed=' + globalThis._curSpeed,
                       'skip=' + (globalThis._animSkipEnabled ? '1' : '0'),
                       'btn_x=' + Math.round(globalThis._btnPosX || 60),
                       'btn_y=' + Math.round(globalThis._btnPosY || 100),
                       'speeds=' + (globalThis._speedsList || []).join(','), ''].join('\n');
            f.writeStringToFile(txt, _path());
        } catch (e) { }
    };
    // ---- diagnostics -----------------------------------------------------
    // Two files, two owners -- they used to share .czn_status and clobber each
    // other, which is why a crash report could show only a JS breadcrumb and
    // none of the injection state:
    //   .czn_status  native only: one line of injection state
    //   .czn_log     this layer: lifecycle lines (boot / attach / re-arm / error)
    // .czn_log is bounded by construction: newest 120 lines, each clipped to
    // 300 chars (so <= ~36KB, typically ~5KB), and a repeated line is dropped
    // instead of appended. No rotation needed -- a session only emits a handful
    // of lines, so the tail covers several sessions. 300 rather than 200 because
    // the longest line is the timeScale crumb ("[TS] ext ... @ <stack>"), whose
    // caller already trims the stack to 160 chars; the useful caller frame sits
    // at the END of it. Full exception text goes to .czn_dump, never here.
    var LOG_LINES = 120;
    var LOG_CLIP = 300;
    globalThis._alog = function (msg) {
        try {
            var f = FU(); if (!f) return;
            var p = f.getWritablePath() + '.czn_log';
            var line = Date.now() + ' ' + msg;
            if (line.length > LOG_CLIP) line = line.substring(0, LOG_CLIP) + '...';
            var old = '';
            try { if (f.isFileExist(p)) old = f.getStringFromFile(p) || ''; } catch (e) { }
            var lines = old.length ? old.split('\n') : [];
            while (lines.length && lines[lines.length - 1] === '') lines.pop();
            if (lines.length && lines[lines.length - 1] === line) return;   // dedupe
            lines.push(line);
            if (lines.length > LOG_LINES) lines = lines.slice(lines.length - LOG_LINES);
            f.writeStringToFile(lines.join('\n') + '\n', p);
        } catch (e) { }
    };
    // breadcrumb: same stream, tagged, so it survives next to the lifecycle
    // lines instead of overwriting the native state file
    globalThis._crumb = function (s) { globalThis._alog('crumb: ' + s); };
    // parse a speed-level list from ",", "，", or whitespace separators:
    // dedup, ascending, keep 1, clamp to [0, 999], force 2..8 entries.
    globalThis._parseLevels = function (str) {
        var s = String(str).replace(/，/g, ',');
        var arr = s.split(/[\s,]+/).map(parseFloat).filter(function (n) { return !isNaN(n) && isFinite(n); });
        var seen = {}, out = [];
        for (var i = 0; i < arr.length; i++) {
            var c = Math.max(0, Math.min(999, Math.round(arr[i] * 100) / 100));
            if (!(c in seen)) { seen[c] = 1; out.push(c); }
        }
        out.sort(function (a, b) { return a - b; });
        if (out.indexOf(1) < 0) out.push(1);
        out.sort(function (a, b) { return a - b; });
        if (out.length < 2) out = [1, 2];
        if (out.length > 8) out = out.slice(0, 8);
        return out;
    };
    __app.registerService('ConfigService', { load: globalThis._loadSpeedConfig, save: globalThis._saveSpeedConfig });
})();
// --- [MODULE END] 04_config ---
"""
sec["04_logger_config.js"] = SEC04

# ================================================================ 05_guard
SEC05 = r"""// --- [MODULE START] 05_guard ---
// Single authority for the "force 1x while a scripted animation plays" guard.
//
// Every release path used to be fire-and-forget: a scene-bound cc.Sequence
// action (dies with the node it runs on), a shared setTimeout handle (any other
// path can clear it, and it is speed-scaled by 00_timers), or nothing at all
// (waiting for an END event that never arrives). Any of those failing left the
// game pinned at 1x. A guard is now a deadline on the wall clock, and the boot
// tick reconciles the live timeScale against _curSpeed, so the release cannot
// be lost -- worst case it lands one tick late.
//
// Reconciliation must cover every channel _setEngineSpeed writes, not just
// director slot 0. A skill cut-in that drops the battle scheduler living in
// another getSchedulerByIndex() slot (or the yuna time_scale env) leaves slot 0
// reading back the user's speed: the ball keeps showing 5x while the battle
// runs at 1x, and a slot-0-only check never sees the drift. Re-picking a level
// fixed it because that path rewrites all slots plus the env.
(function () {
    var ST = { until: 0, since: 0, reason: '', cb: null };
    var HARD_MAX = 60000;      // no guard outlives this, whatever its reason
    var LEGACY_GRACE = 10000;  // flag raised by an unmigrated path, no deadline
    var RECO_MS = 300;         // min gap between reconciliations
    var TS_LOG_MAX = 24;       // external timeScale writes worth recording
    var _lastReco = 0;
    var _selfWrite = false;
    var _tsLogs = 0;
    var _lastBad = '';
    var _envOk = -1;           // -1 unknown, 0 engine ignores the env, 1 readable

    function _spd() {
        var v = globalThis._curSpeed;
        if (typeof v !== 'number' || !isFinite(v) || v <= 0) return 1;
        return v;
    }
    // guard durations were written in in-game ms and used to be scaled by the
    // hooked setTimeout; keep that effective duration without the timer
    function _toWall(ms) {
        var w = ms / _spd();
        if (w < 200) w = 200;
        if (w > 30000) w = 30000;
        return w;
    }

    globalThis._guardState = ST;

    // every channel the game can drop to 1x: the director's scheduler slots
    // (the battle scheduler is often not slot 0) plus the engine env
    function _schedList() {
        var out = [];
        try {
            var dir = cc.Director.getInstance();
            var main = (dir && dir.getScheduler) ? dir.getScheduler() : null;
            if (main) out.push(main);
            if (dir && typeof dir.getSchedulerByIndex === 'function') {
                for (var i = 0; i < 5; i++) {
                    try {
                        var s = dir.getSchedulerByIndex(i);
                        if (s && out.indexOf(s) < 0) out.push(s);
                    } catch (e) { }
                }
            }
        } catch (e) { }
        return out;
    }

    globalThis._setEngineSpeed = function (v) {
        _selfWrite = true;
        var ok = false;
        try {
            var list = _schedList();
            for (var i = 0; i < list.length; i++) {
                try {
                    if (typeof list[i].setTimeScale === 'function') { list[i].setTimeScale(v); ok = true; }
                } catch (e) { }
            }
            if (typeof yuna !== 'undefined' && yuna && yuna.setenv) {
                yuna.setenv('time_scale', v);
                ok = true;
                if (_envOk < 0) {          // does this engine read the env back?
                    try {
                        var ev = (typeof yuna.getenv === 'function') ? parseFloat(yuna.getenv('time_scale')) : NaN;
                        _envOk = (!isNaN(ev) && Math.abs(ev - v) < 0.005) ? 1 : 0;
                        globalThis._slog('[GUARD] env channel ' + (_envOk ? 'ok' : 'n/a'));
                    } catch (e) { _envOk = 0; }
                }
            }
        } catch (e) { }
        _selfWrite = false;
        return ok;
    };

    // observer only -- never rewrites the value. Records game-side writes so
    // .czn_log shows which code path dropped the engine off-speed.
    function _hookSched(list) {
        for (var i = 0; i < list.length; i++) {
            var sc = list[i];
            try {
                if (!sc || sc.__cznTSHooked || typeof sc.setTimeScale !== 'function') continue;
                sc.__cznTSHooked = true;
                var orig = sc.setTimeScale;
                if (orig.__cznWrap) continue;
                var w = function (v) {
                    try {
                        if (!_selfWrite) {
                            var want = globalThis._curSpeed;
                            if (typeof v === 'number' && typeof want === 'number' && Math.abs(v - want) > 0.005) {
                                // stack[0]="Error", stack[1]=this wrapper (noise), so
                                // start at 2: those are the game's own frames. Trim the
                                // "    at " indent and keep 3 -- 200 chars is then all
                                // signal, and it still fits the 300-char log line.
                                var stk = '';
                                try {
                                    var fr = String(new Error().stack || '').split('\n').slice(2, 5);
                                    for (var fi = 0; fi < fr.length; fi++) fr[fi] = String(fr[fi]).replace(/^\s+/, '');
                                    stk = fr.join(' | ');
                                } catch (e) { }
                                var line = '[TS] ext ' + v + ' want ' + want + ' @ ' + stk.substring(0, 200);
                                globalThis._slog(line);
                                if (_tsLogs < TS_LOG_MAX) { _tsLogs++; globalThis._crumb(line); }
                            }
                        }
                    } catch (e) { }
                    return orig.call(this, v);
                };
                w.__cznWrap = true;
                sc.setTimeScale = w;
            } catch (e) { }
        }
    }

    // unconditional: _curSpeed is the user's intent and is never rewritten
    // while a guard is up, so putting it back is always the right move
    globalThis._restoreSpeed = function () {
        var v = globalThis._curSpeed;
        if (typeof v !== 'number' || !isFinite(v) || v < 0) v = 1;
        globalThis._setEngineSpeed(v);
        globalThis._slog('[GUARD] restore ' + v + 'x');
    };

    // the game can re-apply its own speed a frame or two after ours lands
    // (skill cast, cut-in teardown, scene swap). No engine timers here on
    // purpose: a setTimeout registered now outlives the V8 context if the
    // engine rebuilds it mid scene-swap, and firing it afterwards calls into a
    // destroyed context (segfault). Clearing the reconcile gate makes the boot
    // tick re-check on its very next tick instead.
    function _replay() {
        globalThis._restoreSpeed();
        _lastReco = 0;
    }

    function _release(why) {
        var cb = ST.cb;
        ST.until = 0; ST.since = 0; ST.reason = ''; ST.cb = null;
        globalThis._sparkGuardActive = false;
        if (cb) { try { cb(); } catch (e) { } }
        _replay();
        globalThis._slog('[GUARD] <<< release (' + why + ')');
        if (why.indexOf('hard') >= 0 || why.indexOf('legacy') >= 0) {
            try { globalThis._crumb('guard-stuck: ' + why); } catch (e) { }
        }
    }

    // ms <= 0 means "held until its END event", capped by HARD_MAX
    globalThis._guardOn = function (ms, reason, cb) {
        var now = Date.now();
        ST.until = (typeof ms === 'number' && ms > 0) ? now + _toWall(ms) : -1;
        if (!ST.since) ST.since = now;
        ST.reason = reason || ST.reason || '?';
        if (typeof cb === 'function') ST.cb = cb;
        globalThis._sparkGuardActive = true;
        globalThis._slog('[GUARD] >>> on ' + ST.reason +
                         (ST.until > 0 ? ' (' + (ST.until - now) + 'ms)' : ' (until end)'));
    };
    // same, but the duration is wall-clock and must not be speed-scaled
    globalThis._guardOnWall = function (ms, reason, cb) {
        globalThis._guardOn(ms * _spd(), reason, cb);
    };
    globalThis._guardOff = function (reason) {
        if (ST.until || globalThis._sparkGuardActive) _release(reason || 'off');
    };
    // push an active guard's release out (an END event landing too early)
    globalThis._guardExtend = function (ms, reason) {
        if (!globalThis._sparkGuardActive) return;
        if (reason) ST.reason = reason;
        ST.until = Date.now() + _toWall(ms);
        globalThis._slog('[GUARD] extend ' + ST.reason + ' (' + _toWall(ms) + 'ms)');
    };

    globalThis._guardTick = function () {
        if (!globalThis._fl(0x400)) return;     // guard disabled by flags
        var now = Date.now();
        var list = _schedList();
        if (list.length > 0) { try { _hookSched(list); } catch (e) { } }
        if (globalThis._sparkGuardActive) {
            if (ST.until > 0) {
                if (now >= ST.until) _release('deadline ' + ST.reason);
            } else {
                if (!ST.since) ST.since = now;
                if (now - ST.since > (ST.until < 0 ? HARD_MAX : LEGACY_GRACE))
                    _release((ST.until < 0 ? 'hard-max ' : 'legacy ') + ST.reason);
            }
            return;
        }
        ST.since = 0;
        // reconcile: nothing may leave the engine running off-speed
        if (now - _lastReco < RECO_MS) return;
        var want = globalThis._curSpeed;
        if (typeof want !== 'number' || !isFinite(want)) return;
        var bad = null;
        for (var i = 0; i < list.length && !bad; i++) {
            try {
                var sc = list[i];
                if (typeof sc.getTimeScale !== 'function') continue;
                var cur = sc.getTimeScale();
                if (typeof cur === 'number' && isFinite(cur) && Math.abs(cur - want) > 0.005) bad = { k: 'slot' + i, v: cur };
            } catch (e) { }
        }
        if (!bad && _envOk === 1) {
            try {
                if (typeof yuna !== 'undefined' && yuna && typeof yuna.getenv === 'function') {
                    var ev = parseFloat(yuna.getenv('time_scale'));
                    if (!isNaN(ev) && Math.abs(ev - want) > 0.005) bad = { k: 'env', v: ev };
                }
            } catch (e) { }
        }
        if (!bad) { _lastBad = ''; _lastReco = now; return; }
        _lastReco = now;
        var sig = bad.k + '=' + bad.v;
        if (sig !== _lastBad) {          // a game loop fighting us must not flood the ring
            _lastBad = sig;
            globalThis._slog('[GUARD] reconcile ' + bad.k + ' ' + bad.v + ' -> ' + want);
        }
        globalThis._restoreSpeed();
    };
})();
// --- [MODULE END] 05_guard ---
"""
sec["05_guard.js"] = SEC05

SEC09 = r"""// --- [MODULE START] 09_speed_ui ---
// Three-state in-game overlay: collapsed ball -> expanded capsule -> more
// panel -> edit dialog. Drawing uses ONLY cc.LayerColor + cc.Label (DrawNode
// caused native crashes). Touch is ccui.Widget.addTouchEventListener when
// available (the engine's working channel), with a global
// EventListenerTouchOneByOne fallback. The ball reading follows the ENGINE's
// actual timeScale, so a guard drops the number to 1 and back for free.
(function () {
    var CAP_W = 136, CAP_H = 60;   // capsule body size
    var BTN_W = 60, BTN_H = CAP_H;// ball size / touch hot-zone (H matches capsule)
    var DOTS_X = 124, ARR_L_X = 19, NUM_X = 56, ARR_R_X = 93; // capsule inner x
    var BALL_A = 70;               // collapsed ball alpha (node opacity stays 255)
    var PAN_W = 304, PAN_H = 288;  // more panel size
    var ED_W = 320, ED_H = 432;    // edit dialog size
    var GAP = 14;                  // panel gap under the capsule
    var HOT_W = 100, HOT_H = 100, HOT_M = 8; // ghost hot-zone (bottom-left corner)
    var HOLD_MS = 1500;            // hold the ball this long to hide
    var REV_HOLD_MS = 700;         // hold the ghost this long to show again
    var TAP_GAP = 700;             // triple-tap window (max gap between taps)
    var GHOST_DEBUG = false;       // TEMP: paint the hot-zone red for eyeballing

    var ui = null;
    globalThis._cznUI = null;
    var mode = 'collapsed';        // collapsed | expanded | more | edit | hidden
    var speedIdx = 0;
    var R = [];
    var drag = null;
    var refs = {};
    var editBuf = '';
    var _lastActual = null, _lastPaused = null, _lastLevelsKey = '';
    var _cznProbed = false;
    // hidden state: nothing is drawn, only an invisible corner hot-zone stays
    // alive so the user can get the UI back (never persisted on purpose).
    var _hidden = false, _ghost = null, _gprev = null;
    var _hold = null, _rev = null;   // { t0 } long-press trackers (wall clock)
    var _tapT = 0, _tapN = 0;        // triple-tap counter
    var _ignoreUntil = 0;            // swallow the release that restores the UI

    // ---- engine / helpers ------------------------------------------------
    function _dir() { return cc.Director.getInstance(); }
    function _win() { return _dir().getWinSize(); }
    function _fmt(v) { return (Math.round(v * 100) / 100).toString(); }
    function _clamp(v) {
        v = parseFloat(v);
        if (isNaN(v) || !isFinite(v)) v = 1;
        return Math.max(0, Math.min(999, Math.round(v * 100) / 100));
    }
    function _levels() { return globalThis._speedsList || [0, 0.5, 1, 3, 5, 10]; }
    function _findIdx(v) {
        var L = _levels();
        for (var i = 0; i < L.length; i++) if (Math.abs(L[i] - v) < 0.001) return i;
        return -1;
    }
    function _normIdx(i) {
        if (i < 0) i = _findIdx(1);
        if (i < 0) i = 0;
        return i;
    }
    function _readActual() {
        try {
            var sc = _dir().getScheduler();
            if (sc && typeof sc.getTimeScale === 'function') {
                var v = sc.getTimeScale();
                if (typeof v === 'number' && isFinite(v)) return Math.round(v * 100) / 100;
            }
        } catch (e) { }
        return globalThis._curSpeed;
    }
    function _isPaused(v) { return (typeof v === 'number' && v <= 0); }
    function _parseLevels(str) {
        if (typeof globalThis._parseLevels === 'function') return globalThis._parseLevels(str);
        var s = String(str).replace(/，/g, ',');
        var arr = s.split(/[\s,]+/).map(parseFloat).filter(function (n) { return !isNaN(n) && isFinite(n); });
        var seen = {}, out = [];
        for (var i = 0; i < arr.length; i++) {
            var c = _clamp(arr[i]);
            if (!(c in seen)) { seen[c] = 1; out.push(c); }
        }
        out.sort(function (a, b) { return a - b; });
        if (out.indexOf(1) < 0) out.push(1);
        out.sort(function (a, b) { return a - b; });
        if (out.length < 2) out = [1, 2];
        if (out.length > 8) out = out.slice(0, 8);
        return out;
    }

    // ---- draw helpers (LayerColor + Label only) -------------------------
    function _color(r, g, b, a) { try { return new cc.Color(r, g, b, a); } catch (e) { return cc.color(r, g, b, a); } }
    function _layer(parent, c, w, h, x, y, z) {
        var l = null; try { l = cc.LayerColor.create(c); } catch (e) { }
        if (!l) return null;
        try { l.setContentSize(cc.size(w, h)); } catch (e) { try { l.setContentSize({ width: w, height: h }); } catch (e2) { } }
        try { l.setPosition(x, y); } catch (e) { }
        try { parent.addChild(l, z || 0); } catch (e) { }
        return l;
    }
    function _label(parent, text, size, cx, cy, z, col, alpha) {
        var t = null;
        try {
            if (cc.Label && cc.Label.createWithTTF) t = cc.Label.createWithTTF(text, 'font/font_main.ttf', size);
            else if (cc.Label && cc.Label.createWithSystemFont) t = cc.Label.createWithSystemFont(text, 'Arial', size);
        } catch (e) { }
        if (!t) return null;
        try { t.setColor(col || cc.color(255, 255, 255)); } catch (e) { }
        try { parent.addChild(t, (z || 0) + 1); } catch (e) { }
        try { t.setPosition(cx, cy); } catch (e) { }
        if (typeof alpha === 'number') { try { t.setOpacity(alpha); } catch (e) { } }
        return t;
    }
    function _dots(parent, cx, cy, col) {
        var s = 4, gap = 6;
        for (var i = 0; i < 3; i++) {
            _layer(parent, col || _color(200, 200, 208, 255), s, s, cx - s / 2, cy + (i - 1) * gap - s / 2, 2);
        }
    }
    function _reg(id, x, y, w, h) { R.push({ id: id, x: x, y: y, w: w, h: h }); }
    function _regCap() {
        _reg('l', refs.capX + 4, refs.capY, 28, CAP_H);
        _reg('num', refs.capX + 32, refs.capY, 48, CAP_H);
        _reg('r', refs.capX + 80, refs.capY, 28, CAP_H);
        _reg('m', refs.capX + 108, refs.capY, 28, CAP_H);
    }
    function _hit(x, y) {
        for (var i = R.length - 1; i >= 0; i--) { var r = R[i]; if (x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h) return r.id; }
        return null;
    }
    function _bc() { return { x: globalThis._btnPosX + BTN_W / 2, y: globalThis._btnPosY + BTN_H / 2 }; }
    function _terr(tag, e) {
        try {
            var m = tag + ': ' + ((e && (e.message || e.stack)) ? (e.message || String(e)) : String(e));
            if (globalThis.__cznLastErr !== m) { globalThis.__cznLastErr = m; globalThis._crumb('touch-err ' + m); }
        } catch (e2) { }
    }
    var _tLog = 0;
    function _tDiag(tag, id, p) {
        if (_tLog >= 12) return;
        _tLog++;
        try { globalThis._crumb('touch ' + tag + ' id=' + (id || '-') + ' p=' + Math.round(p.x) + ',' + Math.round(p.y) + ' mode=' + mode); } catch (e) { }
    }

    // ---- touch channel (ccui.Widget first, EventListener fallback) ------
    function _ccuiAvailable() {
        try {
            if (typeof ccui === 'undefined' || !ccui.Widget || !ccui.Widget.create) return false;
            var w = ccui.Widget.create();
            var ok = (w && typeof w.addTouchEventListener === 'function' && typeof w.setTouchEnabled === 'function');
            try { if (w) w.removeFromParent(); } catch (e) { }
            return ok ? true : false;
        } catch (e) { return false; }
    }
    function _tcoord(sender, state, x, y) {
        var pos;
        if (typeof x === 'number' && typeof y === 'number') pos = { x: x, y: y };
        else if (state === 0 && typeof sender.getTouchBeganPosition === 'function') pos = sender.getTouchBeganPosition();
        else if (state === 1 && typeof sender.getTouchMovePosition === 'function') pos = sender.getTouchMovePosition();
        else if (typeof sender.getTouchEndPosition === 'function') pos = sender.getTouchEndPosition();
        else pos = { x: 0, y: 0 };
        if (Array.isArray(pos)) pos = { x: pos[0], y: pos[1] };
        if (!pos || typeof pos.x !== 'number') pos = { x: 0, y: 0 };
        return pos;
    }
    function _makeWidget(w, h) {
        var wg = null;
        try { wg = ccui.Widget.create(); } catch (e) { }
        if (!wg) return null;
        try { wg.setAnchorPoint(0, 0); } catch (e) { }
        try { wg.setContentSize(cc.size(w, h)); } catch (e) { try { wg.setContentSize({ width: w, height: h }); } catch (e2) { } }
        try { wg.setTouchEnabled(globalThis._fl(0x1000)); } catch (e) { }
        try {
            wg.addTouchEventListener(function (sender, state, x, y) {
                try {
                    var pos = _tcoord(sender, state, x, y);
                    if (state === 0) _onTouchBegan(pos);
                    else if (state === 1) _onTouchMoved(pos);
                    else _onTouchEnded(pos);
                } catch (e) { _terr('ccui', e); }
            });
        } catch (e) { }
        return wg;
    }
    function _mkContainer(w, h, x, y, z) {
        var node;
        if (ui && ui.useCcui) {
            node = _makeWidget(w, h);
        } else {
            try { node = (cc.Node && cc.Node.create) ? cc.Node.create() : new cc.Node(); } catch (e) { node = new cc.Node(); }
            try { node.setContentSize(cc.size(w, h)); } catch (e) { }
            try { node.setAnchorPoint(0, 0); } catch (e) { }
        }
        if (node) {
            try { node.setPosition(x, y); } catch (e) { }
            try { ui.scene.addChild(node, z); } catch (e) { }
        }
        return node;
    }
    function _installListener() {
        if (globalThis._cznListener) return true;
        try {
            var disp = _dir().getEventDispatcher();
            if (!disp || !cc.EventListenerTouchOneByOne || !cc.EventListenerTouchOneByOne.create) return false;
            var listener = cc.EventListenerTouchOneByOne.create();
            try { if (typeof listener.setSwallowTouches === 'function') listener.setSwallowTouches(true); } catch (e) { }
            listener.onTouchBegan = function (touch, event) { try { return _onTouchBegan(touch.getLocation()); } catch (e) { _terr('em-began', e); return false; } };
            listener.onTouchMoved = function (touch, event) { try { _onTouchMoved(touch.getLocation()); } catch (e) { _terr('em-moved', e); } };
            listener.onTouchEnded = function (touch, event) { try { _onTouchEnded(touch.getLocation()); } catch (e) { _terr('em-ended', e); } };
            listener.onTouchCancelled = function (touch, event) { drag = null; };
            disp.addEventListenerWithFixedPriority(listener, -128);
            globalThis._cznListener = listener;
            return true;
        } catch (e) { return false; }
    }

    // ---- ball painting ---------------------------------------------------
    function _paintBall(forceA) {
        if (!ui || !ui.btn) return;
        var node = ui.btn;
        try { node.removeAllChildren(); } catch (e) { }
        var paused = _isPaused(_readActual());
        var al = (typeof forceA === 'number') ? forceA : ((mode === 'collapsed') ? BALL_A : 255);
        var c = paused ? [200, 60, 60, al] : [24, 24, 30, al];
        _layer(node, _color(c[0], c[1], c[2], c[3]), BTN_W, BTN_H, 0, 0, 0);
        if (globalThis._animSkipEnabled) {
            _layer(node, _color(255, 255, 255, al), 26, 4, (BTN_W - 26) / 2, BTN_H - 8, 1);
        }
        var a = _readActual();
        refs.ballNum = _label(node, paused ? '||' : _fmt(a), 30, BTN_W / 2, BTN_H / 2, 2, null, al);
        R = [];
        _reg('ball', globalThis._btnPosX, globalThis._btnPosY, BTN_W, BTN_H);
    }
    function _pinBallOpaque() {
        // Alpha now lives on the ball's LayerColor (see BALL_A); ccui.Widget
        // does not cascade setOpacity to children, so pin the node at 255.
        if (!ui || !ui.btn) return;
        try { ui.btn.setOpacity(255); } catch (e) { }
    }

    // ---- state builders --------------------------------------------------
    function _clearOverlayNodes() {
        if (refs.capsule) { try { refs.capsule.removeFromParent(); } catch (e) { } refs.capsule = null; }
        if (refs.panel) { try { refs.panel.removeFromParent(); } catch (e) { } refs.panel = null; }
        if (refs.edit) { try { refs.edit.removeFromParent(); } catch (e) { } refs.edit = null; }
        refs.capX = undefined;
        refs.capNum = null; refs.panelBig = null;
    }
    function _goCollapsed() {
        _clearOverlayNodes();
        mode = 'collapsed';
        if (ui && ui.btn) { try { ui.btn.setVisible(true); } catch (e) { } }
        _paintBall();
        _pinBallOpaque();
    }

    // ---- hidden state ----------------------------------------------------
    // Wall clock on purpose: 00_timers scales setTimeout by the game speed, so
    // a 1.5s hold would fire in 75ms at 20x. Date.now() is never scaled.
    function _now() { try { return Date.now(); } catch (e) { return 0; } }
    function _killGhost() {
        if (_ghost) { try { _ghost.removeFromParent(); } catch (e) { } _ghost = null; }
    }
    function _buildGhost() {
        _killGhost();
        if (!ui || !ui.scene) return;
        // an empty widget with a size but no children: nothing is drawn, yet
        // hitTest still passes on its contentSize, so it can take touches.
        var node = _mkContainer(HOT_W, HOT_H, HOT_M, HOT_M, 99995);
        if (!node) return;
        try { if (typeof node.setSwallowTouches === 'function') node.setSwallowTouches(false); } catch (e) { }
        if (GHOST_DEBUG) {
            // TEMP: draw the hot-zone so its position can be eyeballed.
            // Children do not affect the widget's hitTest (that uses its own
            // contentSize), so this is purely visual.
            _layer(node, _color(230, 40, 40, 130), HOT_W, HOT_H, 0, 0, 1);
            _label(node, 'H ' + HOT_W + 'x' + HOT_H, 16, HOT_W / 2, HOT_H / 2, 2, _color(255, 255, 255, 255));
        }
        _ghost = node;
        R = [];
        _reg('ghost', HOT_M, HOT_M, HOT_W, HOT_H);
    }
    // TEMP: a non-interactive twin of the hot-zone, always on screen while
    // GHOST_DEBUG is on, so its position can be checked without hiding first.
    function _killGhostPreview() {
        if (_gprev) { try { _gprev.removeFromParent(); } catch (e) { } _gprev = null; }
    }
    function _buildGhostPreview() {
        _killGhostPreview();
        if (!GHOST_DEBUG || !ui || !ui.scene) return;
        var n = _mkContainer(HOT_W, HOT_H, HOT_M, HOT_M, 99996);
        if (!n) return;
        try { if (typeof n.setTouchEnabled === 'function') n.setTouchEnabled(false); } catch (e) { }
        _layer(n, _color(230, 40, 40, 130), HOT_W, HOT_H, 0, 0, 1);
        _label(n, 'H ' + HOT_W + 'x' + HOT_H, 16, HOT_W / 2, HOT_H / 2, 2, _color(255, 255, 255, 255));
        _gprev = n;
    }
    function _enterHidden() {
        if (!ui || !ui.btn) return;
        _clearOverlayNodes();
        _killGhost();
        _hold = null; _rev = null; _tapN = 0; _tapT = 0;
        drag = null;
        mode = 'hidden';
        _hidden = true;
        R = [];
        try { ui.btn.setVisible(false); } catch (e) { }
        try { if (typeof ui.btn.setTouchEnabled === 'function') ui.btn.setTouchEnabled(false); } catch (e) { }
        _buildGhost();
        try { globalThis._crumb('ui hidden'); } catch (e) { }
    }
    function _exitHidden() {
        _hidden = false;
        _killGhost();
        _hold = null; _rev = null; _tapN = 0; _tapT = 0;
        if (!ui || !ui.btn) { mode = 'collapsed'; return; }
        try { ui.btn.setVisible(true); } catch (e) { }
        try { if (typeof ui.btn.setTouchEnabled === 'function') ui.btn.setTouchEnabled(true); } catch (e) { }
        _goCollapsed();
        _lastActual = null; _lastPaused = null;
        _ignoreUntil = _now() + 300;
        try { globalThis._crumb('ui shown'); } catch (e) { }
    }
    function _tickHolds() {
        var now = _now();
        if (!_hidden && _hold && mode === 'collapsed' && (now - _hold.t0) >= HOLD_MS) { _hold = null; _enterHidden(); return; }
        if (_hidden && _rev && (now - _rev.t0) >= REV_HOLD_MS) { _rev = null; _exitHidden(); }
    }
    function _buildCapsule() {
        _clearOverlayNodes();
        if (!ui || !ui.btn) return;
        try { ui.btn.setVisible(false); } catch (e) { }
        var c = _bc();
        var W = _win();
        var capX = Math.max(4, Math.min(W.width - CAP_W - 4, c.x - CAP_W / 2));
        var capY = Math.max(4, Math.min(W.height - CAP_H - 4, c.y - CAP_H / 2));
        var node = _mkContainer(CAP_W, CAP_H, capX, capY, 99990);
        refs.capsule = node; refs.capX = capX; refs.capY = capY;
        _layer(node, _color(36, 36, 44, 235), CAP_W, CAP_H, 0, 0, 0);
        var L = _levels();
        var lc = (speedIdx <= 0) ? _color(90, 92, 100, 255) : _color(245, 245, 248, 255);
        var rc = (speedIdx >= L.length - 1) ? _color(90, 92, 100, 255) : _color(245, 245, 248, 255);
        _dots(node, DOTS_X, CAP_H / 2);
        _label(node, '<<', 18, ARR_L_X, CAP_H / 2, 2, lc);
        _label(node, '>>', 18, ARR_R_X, CAP_H / 2, 2, rc);
        refs.capNum = _label(node, _fmt(_readActual()), 24, NUM_X, CAP_H / 2, 2);
        R = [];
        _regCap();
        mode = 'expanded';
        _pinBallOpaque();
    }
    function _buildPanel() {
        if (!refs.capsule) { _buildCapsule(); }
        if (refs.panel) { try { refs.panel.removeFromParent(); } catch (e) { } refs.panel = null; }
        if (refs.edit) { try { refs.edit.removeFromParent(); } catch (e) { } refs.edit = null; }
        var c = _bc();
        var W = _win();
        var panX = Math.max(4, Math.min(W.width - PAN_W - 4, c.x - PAN_W / 2));
        var panY = Math.max(4, Math.min(W.height - PAN_H - 4, (refs.capY !== undefined ? refs.capY : c.y) - GAP - PAN_H));
        var node = _mkContainer(PAN_W, PAN_H, panX, panY, 99991);
        refs.panel = node;
        _layer(node, _color(28, 28, 36, 245), PAN_W, PAN_H, 0, 0, 0);
        var pad = 12;
        _label(node, '游戏速度', 15, pad + 30, PAN_H - pad - 22, 1, _color(200, 200, 208, 255));
        var a = _readActual();
        refs.panelBig = _label(node, _isPaused(a) ? '0' : _fmt(a), 26, PAN_W - pad - 44, PAN_H - pad - 22, 1);
        _label(node, '倍', 14, PAN_W - pad - 12, PAN_H - pad - 22, 1, _color(200, 200, 208, 255));
        var L = _levels(), n = L.length;
        var segW = (PAN_W - pad * 2 - 3 * (n - 1)) / n, segH = 40, segY = 184;
        for (var i = 0; i < n; i++) {
            var sx = pad + i * (segW + 3);
            var act = (i === speedIdx);
            _layer(node, act ? _color(83, 74, 183, 255) : _color(42, 42, 51, 255), segW, segH, sx, segY, 2);
            _label(node, _fmt(L[i]), 15, sx + segW / 2, segY + segH / 2, 3);
        }
        var ty = 132;
        _label(node, '跳过动画', 15, pad + 30, ty + 22, 1, _color(200, 200, 208, 255));
        var swX = PAN_W - pad - 52, swW = 40, swH = 24, swY = ty + 10;
        _layer(node, globalThis._animSkipEnabled ? _color(83, 74, 183, 255) : _color(58, 58, 66, 255), swW, swH, swX, swY, 2);
        _layer(node, _color(255, 255, 255, 255), 16, 16, swX + (globalThis._animSkipEnabled ? 20 : 4), swY + 4, 3);
        var ey = 80;
        _layer(node, _color(42, 42, 51, 255), PAN_W - pad * 2, 44, pad, ey, 2);
        _label(node, '编辑档位', 16, PAN_W / 2, ey + 22, 3);
        var hy = 12;
        _layer(node, _color(42, 42, 51, 255), PAN_W - pad * 2, 56, pad, hy, 2);
        _label(node, '隐藏悬浮窗', 15, PAN_W / 2, hy + 36, 3, _color(245, 245, 248, 255));
        _label(node, '左下角连点三次 / 长按恢复', 12, PAN_W / 2, hy + 17, 3, _color(150, 150, 160, 255));
        R = [];
        _regCap();
        for (var j = 0; j < n; j++) _reg('seg' + j, panX + pad + j * (segW + 3), panY + segY, segW, segH);
        _reg('skip', panX + swX, panY + swY, swW, swH);
        _reg('edit', panX + pad, panY + ey, PAN_W - pad * 2, 44);
        _reg('hide', panX + pad, panY + hy, PAN_W - pad * 2, 56);
        mode = 'more';
        _pinBallOpaque();
    }
    function _buildEdit() {
        if (refs.edit) { try { refs.edit.removeFromParent(); } catch (e) { } refs.edit = null; }
        if (!refs.panel) { _buildPanel(); }
        var W = _win();
        var edX = Math.max(4, (W.width - ED_W) / 2);
        var edY = Math.max(4, (W.height - ED_H) / 2);
        var node = _mkContainer(ED_W, ED_H, edX, edY, 99992);
        refs.edit = node;
        _layer(node, _color(30, 30, 38, 252), ED_W, ED_H, 0, 0, 0);
        var pad = 12;
        _label(node, '编辑档位', 18, ED_W / 2, ED_H - 26, 1);
        _label(node, '0 ~ 999，2~8 个档位，逗号分隔', 12, ED_W / 2, ED_H - 48, 1, _color(150, 150, 160, 255));
        _label(node, editBuf === '' ? ' ' : editBuf, 22, ED_W / 2, 350, 1);
        _label(node, '将应用：' + _parseLevels(editBuf).join(' · '), 12, ED_W / 2, 318, 1, _color(150, 150, 160, 255));
        var rows = [['1', '2', '3'], ['4', '5', '6'], ['7', '8', '9'], ['.', '0', ',']];
        var kw = 92, kh = 48, gap = 8, topY = 284;
        var keyIds = [];
        for (var r = 0; r < 4; r++) {
            var cy = topY - r * (kh + gap) - kh / 2;
            for (var q = 0; q < 3; q++) {
                var ch = rows[r][q];
                var cx = pad + q * (kw + gap) + kw / 2;
                _layer(node, _color(42, 42, 51, 255), kw, kh, cx - kw / 2, cy - kh / 2, 2);
                _label(node, ch, 20, cx, cy, 3);
                keyIds.push({ id: 'k' + ch, x: cx - kw / 2, y: cy - kh / 2 });
            }
        }
        var bottomY = 36;
        var bkeys = [['kdel', '删除'], ['cancel', '取消'], ['ok', '应用']];
        for (var b = 0; b < 3; b++) {
            var bcx = pad + b * (kw + gap) + kw / 2;
            _layer(node, b === 2 ? _color(83, 74, 183, 255) : _color(42, 42, 51, 255), kw, kh, bcx - kw / 2, bottomY - kh / 2, 2);
            _label(node, bkeys[b][1], 17, bcx, bottomY, 3);
            keyIds.push({ id: bkeys[b][0], x: bcx - kw / 2, y: bottomY - kh / 2 });
        }
        R = [];
        _regCap();
        for (var k = 0; k < keyIds.length; k++) _reg(keyIds[k].id, edX + keyIds[k].x, edY + keyIds[k].y, kw, kh);
        mode = 'edit';
        _pinBallOpaque();
    }

    // ---- input -----------------------------------------------------------
    function _onTouchBegan(p) {
        var id = _hit(p.x, p.y);
        _tDiag('began', id, p);
        if (id === null) return false;
        if (_hidden) {
            // Never swallow while hidden: the game still gets the touch, we
            // only count taps and start the hold timer.
            if (id === 'ghost') {
                var now = _now();
                if (now > 0 && _tapT > 0 && (now - _tapT) <= TAP_GAP) _tapN++; else _tapN = 1;
                _tapT = now;
                _rev = { t0: now };
                if (_tapN >= 3) { _tapN = 0; _rev = null; _exitHidden(); }
            }
            return false;
        }
        if (mode === 'collapsed' && id === 'ball') { drag = { start: p, moved: false }; _hold = { t0: _now() }; }
        else drag = null;
        return true;
    }
    function _onTouchMoved(p) {
        if (drag && mode === 'collapsed' && ui && ui.btn) {
            if (!drag.moved && Math.abs(p.x - drag.start.x) + Math.abs(p.y - drag.start.y) > 12) { drag.moved = true; _hold = null; }
            if (drag.moved) {
                var W = _win();
                globalThis._btnPosX = Math.round(Math.max(4, Math.min(W.width - BTN_W - 4, p.x - BTN_W / 2)));
                globalThis._btnPosY = Math.round(Math.max(4, Math.min(W.height - BTN_H - 4, p.y - BTN_H / 2)));
                try { ui.btn.setPosition(globalThis._btnPosX, globalThis._btnPosY); } catch (e) { }
                if (!drag.solid) { drag.solid = true; _paintBall(255); }
                R = [];
                _reg('ball', globalThis._btnPosX, globalThis._btnPosY, BTN_W, BTN_H);
            }
        }
    }
    function _step(d) {
        var L = _levels();
        var base = _normIdx(speedIdx);
        var ni = Math.max(0, Math.min(L.length - 1, base + d));
        if (ni === speedIdx) return;
        speedIdx = ni;
        _apply(L[ni]);
    }
    function _apply(v) {
        v = _clamp(v);
        globalThis._curSpeed = v;
        try { if (globalThis._sparkGuardActive) globalThis._guardOff('user-set'); } catch (e) { }
        try { globalThis._setEngineSpeed(v); } catch (e) { }
        if (v > 1) { try { if (typeof globalThis._ensureGuardsInstalled === 'function') globalThis._ensureGuardsInstalled(); } catch (e) { } }
        speedIdx = _normIdx(_findIdx(v));
        try { globalThis._saveSpeedConfig(); } catch (e) { }
        globalThis._slog('speed=' + v);
        _lastActual = null; _lastPaused = null;
    }
    function _applyLevels(arr) {
        globalThis._speedsList = arr;
        globalThis._curSpeed = 1;
        try { if (globalThis._sparkGuardActive) globalThis._guardOff('level-edit'); } catch (e) { }
        try { globalThis._setEngineSpeed(1); } catch (e) { }
        speedIdx = _normIdx(_findIdx(1));
        try { globalThis._saveSpeedConfig(); } catch (e) { }
        globalThis._slog('levels=' + arr.join(','));
        _lastActual = null; _lastPaused = null; _lastLevelsKey = arr.join(',');
    }
    function _onTouchEnded(p) {
        if (_hidden) {
            var rh = _rev ? (_now() - _rev.t0) : 0;
            _rev = null; drag = null; _hold = null;
            // A 0.7s hold is shorter than one tick (0.5s), so the release must
            // be able to finish the hold itself instead of waiting for a tick.
            if (rh >= REV_HOLD_MS) _exitHidden();
            return;
        }
        if (_ignoreUntil && _now() < _ignoreUntil) { _ignoreUntil = 0; drag = null; return; }
        var wasDrag = drag && drag.moved; drag = null;
        var held = _hold ? (_now() - _hold.t0) : 0;
        _hold = null;
        // the tick may not have run yet: honour a completed hold right here
        if (!wasDrag && held >= HOLD_MS) { _enterHidden(); return; }
        if (wasDrag) { try { globalThis._saveSpeedConfig(); } catch (e) { } _paintBall(); return; }
        var id = _hit(p.x, p.y);
        _tDiag('ended', id, p);
        if (mode === 'edit') {
            if (id === 'cancel') { _buildPanel(); return; }
            if (id === 'ok') { var L = _parseLevels(editBuf); if (L && L.length >= 2) { _applyLevels(L); } _buildPanel(); return; }
            if (id === 'kdel') { editBuf = editBuf.slice(0, -1); _buildEdit(); return; }
            if (id && id.length === 2 && id.charAt(0) === 'k') { if (editBuf.length < 40) editBuf += id.charAt(1); _buildEdit(); return; }
            if (id === 'num') { _goCollapsed(); return; }
            if (id === 'l') { _step(-1); _buildEdit(); return; }
            if (id === 'r') { _step(1); _buildEdit(); return; }
            if (id === 'm') { _buildCapsule(); return; }
            if (id === null) { _buildPanel(); return; }
            return;
        }
        if (mode === 'more') {
            if (id === 'num') { _goCollapsed(); return; }
            if (id === 'm') { _buildCapsule(); return; }
            if (id === 'l') { _step(-1); _buildPanel(); return; }
            if (id === 'r') { _step(1); _buildPanel(); return; }
            if (id === 'skip') { try { if (typeof globalThis._toggleCardSkip === 'function') globalThis._toggleCardSkip(); } catch (e) { } _buildPanel(); return; }
            if (id === 'edit') { editBuf = _levels().join(','); _buildEdit(); return; }
            if (id === 'hide') { _enterHidden(); return; }
            if (id && id.indexOf('seg') === 0) { var si = parseInt(id.substring(3), 10); var Lv = _levels(); if (!isNaN(si) && Lv[si] !== undefined) { speedIdx = si; _apply(Lv[si]); } _buildPanel(); return; }
            if (id === null) { _goCollapsed(); return; }
            return;
        }
        if (mode === 'expanded') {
            if (id === 'num') { _goCollapsed(); return; }
            if (id === 'm') { _buildPanel(); return; }
            if (id === 'l') { _step(-1); _buildCapsule(); return; }
            if (id === 'r') { _step(1); _buildCapsule(); return; }
            if (id === null) { _goCollapsed(); return; }
            return;
        }
        if (id === 'ball') { _buildCapsule(); return; }
    }

    function _probeOnce() {
        if (_cznProbed) return;
        _cznProbed = true;
        try {
            var r = {
                ccui: _ccuiAvailable() ? 1 : 0,
                eventManager: (_dir() && typeof _dir().getEventDispatcher === 'function') ? 1 : 0,
                oneByOne: (cc.EventListenerTouchOneByOne && cc.EventListenerTouchOneByOne.create) ? 1 : 0,
                scheduler: (function () { try { var sc = _dir().getScheduler(); return (sc && typeof sc.getTimeScale === 'function') ? 1 : 0; } catch (e) { return 0; } })()
            };
            globalThis._crumb('probe: ' + ((typeof JSON !== 'undefined' && JSON.stringify) ? JSON.stringify(r) : String(r)) + ' path: ' + (ui ? ui.path : '?'));
        } catch (e) { }
    }
    function _attach(scene) {
        if (!scene) return { ok: false, why: 'no-scene' };
        if (!globalThis._fl(0x100)) return { ok: false, why: 'ui-off' };
        if (ui && ui.btn && ui.btn.getParent() === scene) {
            if (_hidden) _enterHidden(); else _paintBall();
            _buildGhostPreview();
            return { ok: true };
        }
        try {
            _clearOverlayNodes();
            _killGhost();
            _killGhostPreview();
            // Our own node from an earlier scene in THIS context: its callbacks
            // belong to the live context, so destroying it is safe. Nodes left
            // over from a previous context are never touched here -- they are
            // made inert by the neutralizer in BOOT (see the comment there).
            if (ui && ui.btn) {
                try { ui.btn.removeFromParent(); } catch (e) { }
                ui = null; globalThis._cznUI = null;
            }
            var useCcui = _ccuiAvailable();
            var node = null;
            if (useCcui) {
                node = _makeWidget(BTN_W, BTN_H);
            } else {
                try { node = (cc.Node && cc.Node.create) ? cc.Node.create() : new cc.Node(); } catch (e) { node = new cc.Node(); }
                try { node.setContentSize(cc.size(BTN_W, BTN_H)); } catch (e) { }
                try { node.setAnchorPoint(0, 0); } catch (e) { }
            }
            if (!node) return { ok: false, why: 'no-node' };
            try { node.setName('__czn_speed_ui'); } catch (e) { }
            try { node.setPosition(globalThis._btnPosX, globalThis._btnPosY); } catch (e) { }
            scene.addChild(node, 99990);
            ui = { btn: node, scene: scene, path: useCcui ? 'ccui' : 'node', useCcui: useCcui };
            globalThis._cznUI = ui;
            if (!useCcui) {
                if (!_installListener()) return { ok: false, why: 'no-touch-channel' };
                ui.path = 'event-manager';
            }
            speedIdx = _normIdx(_findIdx(globalThis._curSpeed));
            if (_hidden) { _enterHidden(); } else { _paintBall(); _pinBallOpaque(); }
            _buildGhostPreview();
            _probeOnce();
            globalThis._alog('attach ok path=' + ui.path +
                ' kids=' + (scene.getChildren ? scene.getChildren().length : -1) +
                ' hidden=' + _hidden);
            return { ok: true };
        } catch (e) { return { ok: false, why: 'build:' + e }; }
    }

    globalThis._cznAttachUI = function (scene) { return _attach(scene); };
    globalThis._applySpeed = _apply;
    globalThis._updateSpeedLabel = function () {
        try {
            if (_hidden) return;
            if (mode === 'collapsed') _paintBall();
            _lastActual = null; _lastPaused = null;
            globalThis._cznRefreshUI();
        } catch (e) { }
    };
    globalThis._cznRefreshUI = function () {
        try {
            _tickHolds();
            if (_hidden) return;
            if (!ui || !ui.btn) return;
            var L = _levels();
            var key = L.join(',');
            if (key !== _lastLevelsKey) {
                _lastLevelsKey = key;
                speedIdx = _normIdx(_findIdx(globalThis._curSpeed));
            }
            var v = _readActual();
            var paused = _isPaused(v);
            if (v !== _lastActual) {
                _lastActual = v;
                if (refs.ballNum && mode === 'collapsed') { try { refs.ballNum.setString(paused ? '||' : _fmt(v)); } catch (e) { } }
                if (refs.capNum) { try { refs.capNum.setString(_fmt(v)); } catch (e) { } }
                if (refs.panelBig) { try { refs.panelBig.setString(paused ? '0' : _fmt(v)); } catch (e) { } }
            }
            if (paused !== _lastPaused) {
                _lastPaused = paused;
                if (mode === 'collapsed') _paintBall();
            }
        } catch (e) { }
    };
    globalThis._slog('ui ready');
})();
// --- [MODULE END] 09_speed_ui ---
"""
sec["09_speed_ui.js"] = SEC09

# ---------------------------------------------------------------- assemble
BOOT = r"""
// --- [mod] native-driven tick: boot -> self-healing UI + keep-alive ---
(function () {
    globalThis.__cznTickN = 0;
    globalThis.__cznLastNote = '';
    try { globalThis._alog('boot eval ctx=' + globalThis.__cznCtxId); } catch (e) { }
    globalThis.__cznBootTick = function () {
        var note = '';
        try {
            globalThis.__cznTickN++;
            // guard deadlines + timeScale reconciliation, every tick
            try { if (typeof globalThis._guardTick === 'function') globalThis._guardTick(); } catch (e) { }
            if (!globalThis.__cznCfgLoaded) {
                globalThis.__cznCfgLoaded = true;
                try { if (typeof globalThis._loadSpeedConfig === 'function') globalThis._loadSpeedConfig(); } catch (e) { }
                try { if (globalThis._curSpeed !== 1 && !globalThis._sparkGuardActive && typeof globalThis._applySpeed === 'function') globalThis._applySpeed(globalThis._curSpeed); } catch (e) { }
                try { if (globalThis._skipOnBoot && !globalThis._animSkipEnabled && typeof globalThis._toggleCardSkip === 'function') globalThis._toggleCardSkip(); } catch (e) { }
            }
            var scene = null;
            try { scene = cc.Director.getInstance().getRunningScene(); } catch (e) { }
            if (!scene) {
                note = 'scene=null';
            } else {
                try {
                    var alive = globalThis._cznUI && globalThis._cznUI.btn && globalThis._cznUI.btn.getParent() === scene;
                    if (!alive && typeof globalThis._cznAttachUI === 'function') {
                        var ar = globalThis._cznAttachUI(scene);
                        if (ar && !ar.ok) note = 'attach-fail: ' + ar.why;
                    }
                } catch (e) { note = 'attach-throw: ' + e; }
                if (!globalThis.__cznReady && globalThis._cznUI && globalThis._cznUI.btn && globalThis._cznUI.btn.getParent() === scene) {
                    globalThis.__cznReady = true;
                    note = 'boot ok path=' + (globalThis._cznUI.path || '?');
                }
                if (globalThis.__cznTickN % 6 === 0) {
                    // speed no longer re-applied here: _guardTick reconciles it
                    // only when the engine actually drifted (no cfg.dat churn)
                    try { if (globalThis._animSkipEnabled && globalThis.AnimSkipService && typeof globalThis.AnimSkipService.refreshHooks === 'function') globalThis.AnimSkipService.refreshHooks(); } catch (e) { }
                }
            }
            // keep the ball reading in sync with the engine's actual timeScale
            try { if (typeof globalThis._cznRefreshUI === 'function') globalThis._cznRefreshUI(); } catch (e) { }
        } catch (e) { note = 'err: ' + e; }
        try {
            if (note && note !== globalThis.__cznLastNote) {
                globalThis.__cznLastNote = note;
                globalThis._crumb(note);
            }
        } catch (e) { }
    };
    globalThis._cznUI = null;

    // ---- tick driver -----------------------------------------------------
    // A scene-anchored RepeatForever action and nothing else. A callback
    // registered on the Director's scheduler, or a setTimeout chain, outlives
    // the scene AND the V8 context: after the engine rebuilds the context the
    // engine still holds the old JS function and firing it segfaults. An action
    // dies with its scene, so the engine releases the CallFunc while the
    // context is still valid.
    //
    // The flip side is that the driver dies on EVERY scene swap, in the same
    // context as well. So it must be re-armable: __cznArmDriver() is idempotent
    // and is called by the native side (from the asset-read hook, i.e. exactly
    // while the game loads the next scene) whenever the probe reports that the
    // driver is no longer parented to the running scene.
    var rep = [], ok = false;
    try {
        var dir = cc.Director.getInstance();
        var tick = function () {
            try { if (typeof globalThis.__cznBootTick === 'function') globalThis.__cznBootTick(); } catch (e) { }
        };

        // Neutralize leftovers from a PREVIOUS V8 context. Such a node still
        // sits in the scene graph and its JS callbacks (the ccui touch listener,
        // the action's CallFunc) point into a context the engine has already
        // destroyed. Destroying it -- removeFromParent() -- releases those
        // handles and segfaults (cocos2d actually releases at pool drain, i.e.
        // at the end of the same frame), so make it inert instead.
        var neutralize = function (scene) {
            try {
                var kids = scene.getChildren ? scene.getChildren() : null;
                var am = null;
                try { am = dir.getActionManager ? dir.getActionManager() : null; } catch (e) { }
                for (var ki = 0; kids && ki < kids.length; ki++) {
                    var kk = kids[ki];
                    if (!kk || typeof kk.getName !== 'function') continue;
                    var nm = '';
                    try { nm = String(kk.getName()); } catch (e) { continue; }
                    if (nm !== '__czn_speed_ui' && nm !== '__czn_tick') continue;
                    globalThis._alog('neutralize ' + nm + ' idx=' + ki);
                    try { kk.setVisible(false); } catch (e) { }
                    if (nm === '__czn_tick' && am && typeof am.pauseTarget === 'function') {
                        try { am.pauseTarget(kk); } catch (e) { }
                    }
                }
            } catch (e) { globalThis._alog('neutralize err ' + e); }
        };

        globalThis.__cznArmDriver = function () {
            try {
                if (!globalThis._fl(0x200)) return '1';
                var scene = dir.getRunningScene ? dir.getRunningScene() : null;
                if (!scene) return '0';
                var cur = globalThis.__cznTickNode;
                if (cur && cur.getParent && cur.getParent() === scene) return '1';
                // Our own driver from an earlier scene in THIS context: its
                // CallFunc belongs to the live context, so releasing it is safe.
                if (cur) {
                    try { cur.stopAllActions(); } catch (e) { }
                    try { cur.removeFromParent(); } catch (e) { }
                    globalThis.__cznTickNode = null;
                }
                neutralize(scene);
                var node = (cc.Node && cc.Node.create) ? cc.Node.create() : new cc.Node();
                try { node.setName('__czn_tick'); } catch (e) { }
                scene.addChild(node);
                globalThis.__cznTickNode = node;
                var sq = cc.Sequence.create(cc.DelayTime.create(0.5), cc.CallFunc.create(tick));
                node.runAction((cc.RepeatForever && cc.RepeatForever.create) ? cc.RepeatForever.create(sq) : sq);
                globalThis._alog('driver armed ctx=' + globalThis.__cznCtxId +
                    ' scene=' + (scene.getName ? String(scene.getName()) : '?'));
                // attach the UI now instead of waiting one tick
                try { globalThis.__cznBootTick(); } catch (e) { }
                return '1';
            } catch (e) { globalThis._alog('arm err ' + e); return '0'; }
        };

        var ar = globalThis.__cznArmDriver();
        rep.push('arm=' + ar);
        ok = (ar === '1');
        globalThis._crumb('install: ' + rep.join(' '));
    } catch (e) {
        try { globalThis._crumb('install fatal: ' + e); } catch (e2) { }
    }
    return ok ? "1" : "0";
})();
"""

order = ["00_timers.js", "03_framework.js", "04_logger_config.js", "05_guard.js",
         "06_spark_guard.js", "07_anim_skip.js", "09_speed_ui.js"]
# Context marker -- the native side probes this global to decide whether this
# V8 context already carries the layer. It must be the FIRST statement so it is
# in place even if a later section throws. Do not compare V8 context pointers
# natively instead: Local<Context> is a HandleScope slot address, not an object
# address, so the same context reports different values on every call.
MARKER = (
    "globalThis.__cznCtxId = (typeof globalThis.__cznCtxId === 'number')\n"
    "    ? globalThis.__cznCtxId\n"
    "    : ((Date.now() % 1000000) * 1000 + Math.floor(Math.random() * 1000));\n"
)
parts = ["// CZN runtime module JS",
         "// sections: " + ", ".join(order), "",
         MARKER]
for name in order:
    parts.append("// ======== " + name + " ========")
    if name in ("06_spark_guard.js", "07_anim_skip.js"):
        parts.append(io.open(os.path.join(here, name), encoding="utf-8").read())
    else:
        parts.append(sec[name])
parts.append(BOOT)

out = "\n".join(parts)

# ---------------------------------------------------------------- shim
n_repl = out.count("(typeof globalThis._SPEED_LEVELS !== 'undefined' && typeof globalThis._speedIdx !== 'undefined') ? globalThis._SPEED_LEVELS[globalThis._speedIdx] : 1")
out = out.replace("(typeof globalThis._SPEED_LEVELS !== 'undefined' && typeof globalThis._speedIdx !== 'undefined') ? globalThis._SPEED_LEVELS[globalThis._speedIdx] : 1",
                  "(globalThis._curSpeed || 1)")

# ---------------------------------------------------------------- visibility
# NOTE: no setTimeout diagnostics here. Every eval re-registers them on the
# engine's timer list, and a timer whose JS callback belongs to a context the
# engine has since destroyed is a dangling call (segfault on fire).
# The dump gets its own file: .czn_status belongs to the native side (injection
# state) and .czn_log to the layer's lifecycle, so an exception dump must not
# overwrite either.
PRELUDE = (
    "(function () {\n"
    "    function _dump() {\n"
    "        try {\n"
    "            var fu = cc.FileUtils.getInstance();\n"
    "            var body = '';\n"
    "            if (globalThis.__modErr) body += 'MOD_ERR:' + globalThis.__modErr + '\\n';\n"
    "            body += 'RING:' + (globalThis._slogDump ? globalThis._slogDump() : '');\n"
    "            fu.writeStringToFile(body, fu.getWritablePath() + '.czn_dump');\n"
    "        } catch (e2) { }\n"
    "    }\n"
    "    globalThis.__modDump = _dump;\n"
    "})();\n"
)
CATCH = (
    "} catch (e) {\n"
    "    globalThis.__modErr = (e && (e.stack || e.message)) || String(e);\n"
    "    if (typeof globalThis.__modDump === 'function') globalThis.__modDump();\n"
    "    throw e;\n"
    "}\n"
)
out = PRELUDE + "try {\n" + out + "\n" + CATCH

# ---------------------------------------------------------------- neutralize
out = out.replace("_speedLog", "_slog")
out = out.replace("SpeedHack", "Mod")
out = out.replace("[SPARK V20]", "[g7]")
out = out.replace("SPARK GUARD", "gd")
out = out.replace("[SKIP]", "[sk]")

assert ")JS" not in out, "raw-string terminator collision"

# ---------------------------------------------------------------- asserts
left = re.findall(r"_SPEED_LEVELS|_speedIdx|_speedCustom", out)
assert not left, "old speed-model refs remain: %d" % len(left)
for need in ["_cznAttachUI", "__cznBootTick", "__cznArmDriver", "registerService", "_toggleCardSkip",
             "addEventListenerWithFixedPriority", "getLocation",
             "function _onTouchBegan(p)", "function _onTouchEnded(p)",
             "_cznRefreshUI", "_buildCapsule", "_buildPanel", "_buildEdit",
             "_parseLevels", "_paintBall", "_crumb",
             "_enterHidden", "_exitHidden", "_buildGhost", "_tickHolds"]:
    assert need in out, "missing: " + need
assert "__app.on" not in out and "registerPage" not in out, "dead framework members remain"
assert "czn_speed v" not in out and "czn-speed v" not in out, "version string leaked"
assert ".czn_install" not in out and ".czn_js_status" not in out and "mod_log" not in out, "stale file refs"

io.open(OUT, "w", encoding="utf-8", newline="\n").write(out)
print("written", OUT, len(out), "bytes,", out.count("\n"), "lines; shim replacements:", n_repl)
