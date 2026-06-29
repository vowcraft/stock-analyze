package com.zyl.stockanalyze.akshare;

import com.fasterxml.jackson.databind.JsonNode;

public final class AkshareResponse {
    private final String function;
    private final JsonNode data;

    public AkshareResponse(String function, JsonNode data) {
        this.function = function;
        this.data = data;
    }

    public String getFunction() {
        return function;
    }

    public JsonNode getData() {
        return data;
    }
}
