package com.zyl.stockanalyze.akshare;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;

import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

public final class AkshareStockService {
    private static final DateTimeFormatter BASIC_DATE = DateTimeFormatter.BASIC_ISO_DATE;

    private final AkshareClient client;
    private volatile Map<String, String> stockNameCache = Collections.emptyMap();

    public AkshareStockService(AkshareClient client) {
        this.client = Objects.requireNonNull(client, "client");
    }

    public ArrayNode getDailyHistory(String symbol, LocalDate startDate, LocalDate endDate, String adjust) {
        Objects.requireNonNull(symbol, "symbol");
        Objects.requireNonNull(startDate, "startDate");
        Objects.requireNonNull(endDate, "endDate");

        Map<String, Object> params = new LinkedHashMap<>();
        params.put("symbol", symbol);
        params.put("period", "daily");
        params.put("start_date", BASIC_DATE.format(startDate));
        params.put("end_date", BASIC_DATE.format(endDate));
        params.put("adjust", adjust == null ? "" : adjust);

        return requireArray("stock_zh_a_hist", client.invoke("stock_zh_a_hist", params).getData());
    }

    public String getStockName(String symbol) {
        Objects.requireNonNull(symbol, "symbol");

        Map<String, String> currentCache = stockNameCache;
        String cachedName = currentCache.get(symbol);
        if (cachedName != null) {
            return cachedName;
        }

        synchronized (this) {
            currentCache = stockNameCache;
            cachedName = currentCache.get(symbol);
            if (cachedName != null) {
                return cachedName;
            }

            Map<String, String> refreshedCache = loadStockNameCache();
            stockNameCache = refreshedCache;
            return refreshedCache.getOrDefault(symbol, symbol);
        }
    }

    private ArrayNode requireArray(String function, JsonNode data) {
        if (data != null && data.isArray()) {
            return (ArrayNode) data;
        }
        throw new AkshareException(function, 0, "Expected AkShare response data to be an array", data, data == null ? "" : data.toString());
    }

    private Map<String, String> loadStockNameCache() {
        ArrayNode rows = requireArray("stock_info_a_code_name", client.invoke("stock_info_a_code_name", Map.of()).getData());
        Map<String, String> cache = new HashMap<>(rows.size());
        for (JsonNode row : rows) {
            String code = row.path("code").asText("");
            String name = row.path("name").asText("");
            if (!code.isBlank() && !name.isBlank()) {
                cache.put(code, name);
            }
        }
        return Collections.unmodifiableMap(cache);
    }
}
