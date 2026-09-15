package dev.caseflow.common;

public class Problem extends RuntimeException {
    public final int status;
    public final boolean retryable;
    public Problem(int status, String message) { this(status, message, false); }
    public Problem(int status, String message, boolean retryable) {
        super(message); this.status = status; this.retryable = retryable;
    }
    public static Problem missing() { return new Problem(404, "Resource not found"); }
    public static Problem forbidden() { return new Problem(403, "This action is not permitted"); }
    public static Problem conflict() { return new Problem(409, "The resource changed. Reload it before trying again."); }
    public static void require(boolean condition, String message) {
        if (!condition) throw new Problem(400, message);
    }
}
