package com.apksmith.test;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;

/**
 * Minimal test Activity for ApkSmith E2E verification.
 *
 * Has three methods with two if/else branches so the instrumented APK
 * produces a deterministic set of log lines:
 *
 *   - onCreate        : entry point, exercised once on launch
 *   - compute(int)    : one if/else branch on the input
 *   - handleResult(int) : another if/else branch
 *
 * The original Log.d calls use tag "HelloApp" so the E2E test can
 * verify the ORIGINAL app still works after instrumentation (logs
 * with "HelloApp" should still appear). The injected logs use tag
 * "ApkSmith" (configurable).
 */
public class MainActivity extends Activity {

    private static final String TAG = "HelloApp";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.d(TAG, "onCreate_begin");
        int r = compute(5);
        handleResult(r);
        Log.d(TAG, "onCreate_end");
    }

    public int compute(int x) {
        Log.d(TAG, "compute_called_with_" + x);
        if (x > 0) {
            Log.d(TAG, "compute_positive_branch");
            return x * 2;
        } else {
            Log.d(TAG, "compute_nonpositive_branch");
            return -1;
        }
    }

    public void handleResult(int r) {
        Log.d(TAG, "handleResult_called_with_" + r);
        if (r > 0) {
            Log.d(TAG, "handleResult_positive");
        } else {
            Log.d(TAG, "handleResult_nonpositive");
        }
    }
}
