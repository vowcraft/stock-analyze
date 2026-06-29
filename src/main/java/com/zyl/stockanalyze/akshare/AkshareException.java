package com.zyl.stockanalyze.akshare;

import com.fasterxml.jackson.databind.JsonNode;

public final class AkshareException extends RuntimeException {
    private final String function;
    private final int exitCode;
    private final JsonNode payload;
    private final String rawOutput;

    public AkshareException(String function, int exitCode, String message, JsonNode payload, String rawOutput) {
        super(message);
        this.function = function;
        this.exitCode = exitCode;
        this.payload = payload;
        this.rawOutput = rawOutput;
    }

    public String getFunction() {
        return function;
    }

    public int getExitCode() {
        return exitCode;
    }

    public JsonNode getPayload() {
        return payload;
    }

    public String getRawOutput() {
        return rawOutput;
    }
}
