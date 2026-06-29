package com.zyl.stockanalyze.notification;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class WeComNotifierTest {
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void shouldSendWebhookTextMessage() throws Exception {
        AtomicReference<String> requestBody = new AtomicReference<>();
        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/cgi-bin/webhook/send", exchange -> {
            requestBody.set(readBody(exchange));
            respond(exchange, "{\"errcode\":0,\"errmsg\":\"ok\"}");
        });
        server.start();
        try {
            String baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
            NotificationSender sender = WeComNotifier.fromEnvironment(Map.of(
                    "WECOM_WEBHOOK_URL", baseUrl + "/cgi-bin/webhook/send?key=test-key"
            ));

            sender.sendText("hello webhook");

            JsonNode payload = objectMapper.readTree(requestBody.get());
            assertEquals("text", payload.path("msgtype").asText());
            assertEquals("hello webhook", payload.path("text").path("content").asText());
        } finally {
            server.stop(0);
        }
    }

    @Test
    void shouldSendAppTextMessageAndCacheToken() throws Exception {
        AtomicInteger tokenCalls = new AtomicInteger();
        AtomicReference<String> requestBody = new AtomicReference<>();
        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/cgi-bin/gettoken", exchange -> {
            tokenCalls.incrementAndGet();
            respond(exchange, "{\"errcode\":0,\"errmsg\":\"ok\",\"access_token\":\"TOKEN123\",\"expires_in\":7200}");
        });
        server.createContext("/cgi-bin/message/send", exchange -> {
            assertTrue(exchange.getRequestURI().toString().contains("access_token=TOKEN123"));
            requestBody.set(readBody(exchange));
            respond(exchange, "{\"errcode\":0,\"errmsg\":\"ok\"}");
        });
        server.start();
        try {
            String baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
            NotificationSender sender = WeComNotifier.fromEnvironment(Map.of(
                    "WECOM_API_BASE_URL", baseUrl,
                    "WECOM_CORP_ID", "corp-id",
                    "WECOM_CORP_SECRET", "corp-secret",
                    "WECOM_AGENT_ID", "1000002",
                    "WECOM_TO_USER", "zhangsan"
            ));

            sender.sendText("hello app");
            sender.sendText("hello app again");

            JsonNode payload = objectMapper.readTree(requestBody.get());
            assertEquals("text", payload.path("msgtype").asText());
            assertEquals("zhangsan", payload.path("touser").asText());
            assertEquals("hello app again", payload.path("text").path("content").asText());
            assertEquals(1, tokenCalls.get());
        } finally {
            server.stop(0);
        }
    }

    @Test
    void shouldSendAppTextMessageToDepartment() throws Exception {
        AtomicReference<String> requestBody = new AtomicReference<>();
        HttpServer server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/cgi-bin/gettoken", exchange -> {
            respond(exchange, "{\"errcode\":0,\"errmsg\":\"ok\",\"access_token\":\"TOKEN123\",\"expires_in\":7200}");
        });
        server.createContext("/cgi-bin/message/send", exchange -> {
            requestBody.set(readBody(exchange));
            respond(exchange, "{\"errcode\":0,\"errmsg\":\"ok\"}");
        });
        server.start();
        try {
            String baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
            NotificationSender sender = WeComNotifier.fromEnvironment(Map.of(
                    "WECOM_API_BASE_URL", baseUrl,
                    "WECOM_CORP_ID", "corp-id",
                    "WECOM_CORP_SECRET", "corp-secret",
                    "WECOM_AGENT_ID", "1000002",
                    "WECOM_TO_PARTY", "1"
            ));

            sender.sendText("hello party");

            JsonNode payload = objectMapper.readTree(requestBody.get());
            assertEquals("1", payload.path("toparty").asText());
            assertEquals("hello party", payload.path("text").path("content").asText());
        } finally {
            server.stop(0);
        }
    }

    @Test
    void shouldDisableWhenNotConfigured() {
        NotificationSender sender = WeComNotifier.fromEnvironment(Map.of());

        assertTrue(!sender.isEnabled());
    }

    @Test
    void shouldFailFastWhenRequiredConfigurationMissing() {
        IllegalStateException exception = assertThrows(
                IllegalStateException.class,
                () -> WeComNotifier.requireFromEnvironment(Map.of())
        );

        assertTrue(exception.getMessage().contains("WeCom notification is required"));
    }

    @Test
    void shouldApplyCodeDefaultsForMainEntry() {
        NotificationSender sender = WeComNotifier.fromEnvironment(WeComNotifier.withCodeDefaults(Map.of()));

        assertTrue(sender.isEnabled());
    }

    private static String readBody(HttpExchange exchange) throws IOException {
        return new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
    }

    private static void respond(HttpExchange exchange, String body) throws IOException {
        byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
        exchange.sendResponseHeaders(200, bytes.length);
        exchange.getResponseBody().write(bytes);
        exchange.close();
    }
}
