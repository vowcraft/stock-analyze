package com.zyl.stockanalyze;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.zyl.stockanalyze.akshare.AkshareStockService;
import com.zyl.stockanalyze.notification.NotificationSender;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Iterator;
import java.util.Map;
import java.util.Objects;

@Component
@ConditionalOnProperty(name = "app.polling.enabled", havingValue = "true", matchIfMissing = true)
public final class StockPollingJob {
    private static final int LOOKBACK_DAYS = 20;
    private static final DateTimeFormatter TIMESTAMP_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
    private static final String DEFAULT_SYMBOL = "600519";

    private final AkshareStockService stockService;
    private final NotificationSender notificationSender;
    private final String symbol;


    public StockPollingJob(
            AkshareStockService stockService,
            NotificationSender notificationSender
    ) {
        this.stockService = Objects.requireNonNull(stockService, "stockService");
        this.notificationSender = Objects.requireNonNull(notificationSender, "notificationSender");
        this.symbol = DEFAULT_SYMBOL;
    }

    @Scheduled(initialDelay = 0L, fixedDelay = 60000L)
    public void run() {
        try {
            LocalDate endDate = LocalDate.now();
            ArrayNode history = stockService.getDailyHistory(symbol, endDate.minusDays(LOOKBACK_DAYS), endDate, "");
            String stockName = stockService.getStockName(symbol);
            if (history.isEmpty()) {
                String message = String.format("[%s] symbol=%s name=%s no data returned", nowText(), symbol, stockName);
                System.out.println(message);
                notificationSender.sendText(message);
                return;
            }

            JsonNode latestBar = history.get(history.size() - 1);
            String consoleMessage = String.format("[%s] symbol=%s name=%s latest=%s", nowText(), symbol, stockName, latestBar);
            System.out.println(consoleMessage);
            notificationSender.sendText(buildWeComMessage(stockName, latestBar));
        } catch (Exception exception) {
            System.err.printf(
                    "[%s] symbol=%s scheduled fetch failed: %s%n",
                    nowText(),
                    symbol,
                    exception.getMessage()
            );
            exception.printStackTrace(System.err);
        }
    }

    private static String nowText() {
        return LocalDateTime.now().format(TIMESTAMP_FORMATTER);
    }

    private String buildWeComMessage(String stockName, JsonNode latestBar) {
        StringBuilder builder = new StringBuilder();
        builder.append("股票监控").append('\n');
        builder.append("时间: ").append(nowText()).append('\n');
        builder.append("代码: ").append(symbol).append('\n');
        builder.append("名称: ").append(stockName).append('\n');

        Iterator<Map.Entry<String, JsonNode>> fields = latestBar.fields();
        while (fields.hasNext()) {
            Map.Entry<String, JsonNode> field = fields.next();
            builder.append(field.getKey()).append(": ").append(asText(field.getValue()));
            if (fields.hasNext()) {
                builder.append('\n');
            }
        }
        return builder.toString();
    }

    private String asText(JsonNode value) {
        if (value == null || value.isNull()) {
            return "";
        }
        return value.isValueNode() ? value.asText() : value.toString();
    }
}
