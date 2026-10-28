package com.czn.mod;

import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

/**
 * LSPosed entry point.
 *
 * Loads the native injector on the game's main process and hands off. All real
 * work (wait for libssr.so, wait for V8, resolve symbols, patch GOT, eval JS)
 * happens inside libczn_core.so; this class is just the loader glue that
 * replaces the Zygisk ABI entry of the original module.
 */
public final class Main implements IXposedHookLoadPackage {

    private static final String INT_PKG = "com.smilegate.chaoszero.stove.google";
    private static final String CN_PKG = "com.tencent.czn";

    static {
        System.loadLibrary("czn_core");
    }

    @Override
    public void handleLoadPackage(XC_LoadPackage.LoadPackageParam lp) {
        if (!lp.isFirstApplication) return;   // only the main process, never forks
        if (!INT_PKG.equals(lp.packageName) && !CN_PKG.equals(lp.packageName)) return;

        XposedBridge.log("[CZN] target matched: " + lp.packageName + " (proc " + lp.processName + ")");
        nativeStart(lp.packageName);
    }

    private static native void nativeStart(String packageName);
}
