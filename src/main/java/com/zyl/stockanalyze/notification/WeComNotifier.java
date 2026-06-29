package com.zyl.stockanalyze.notification;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

public final class WeComNotifier implements NotificationSender {
    private static final String DEFAULT_API_BASE_URL = "https://qyapi.weixin.qq.com";
    private static final Duration HTTP_TIMEOUT = Duration.ofSeconds(10);
    private static final String DEFAULT_CORP_ID = "wwad4729df5fff92cf";
    private static final String DEFAULT_CORP_SECRET = "E8KRmh7MmDj1fakhqkyeKeZxswq4AH6pm3NGkmiL8GA";
    private static final String DEFAULT_AGENT_ID = "1000002";
    private static final String DEFAULT_TO_PARTY = "1";

    private final Mode mode;
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final URI webhookUri;
    private final String apiBaseUrl;
    private final String corpId;
    private final String corpSecret;
    private final String agentId;
    private final String toUser;
    private final String toParty;
    private final String toTag;

    private volatile AccessToken accessToken = AccessToken.expired();

    private WeComNotifier(
            Mode mode,
            HttpClient httpClient,
            ObjectMapper objectMapper,
            URI webhookUri,
            String apiBaseUrl,
            String corpId,
            String corpSecret,
            String agentId,
            String toUser,
            String toParty,
            String toTag
    ) {
        this.mode = Objects.requireNonNull(mode, "mode");
        this.httpClient = Objects.requireNonNull(httpClient, "httpClient");
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper");
        this.webhookUri = webhookUri;
        this.apiBaseUrl = apiBaseUrl;
        this.corpId = corpId;
        this.corpSecret = corpSecret;
        this.agentId = agentId;
        this.toUser = toUser;
        this.toParty = toParty;
        this.toTag = toTag;
    }

    public static NotificationSender fromEnvironment() {
        return fromEnvironment(withCodeDefaults(System.getenv()));
    }

    public static NotificationSender requireFromEnvironment() {
        return requireFromEnvironment(withCodeDefaults(System.getenv()));
    }

    static NotificationSender fromEnvironment(Map<String, String> environment) {
        Objects.requireNonNull(environment, "environment");

        String webhookUrl = trimToNull(environment.get("WECOM_WEBHOOK_URL"));
        String webhookKey = trimToNull(environment.get("WECOM_WEBHOOK_KEY"));
        if (webhookUrl != null || webhookKey != null) {
            String webhookBaseUrl = trimToNull(environment.get("WECOM_WEBHOOK_BASE_URL"));
            URI resolvedWebhookUri = URI.create(
                    webhookUrl != null
                            ? webhookUrl
                            : normalizeBaseUrl(webhookBaseUrl == null ? DEFAULT_API_BASE_URL : webhookBaseUrl)
                            + "/cgi-bin/webhook/send?key=" + urlEncode(webhookKey)
            );
            return new WeComNotifier(
                    Mode.WEBHOOK,
                    HttpClient.newHttpClient(),
                    new ObjectMapper(),
                    resolvedWebhookUri,
                    null,
                    null,
                    null,
                    null,
                    null,
                    null,
                    null
            );
        }

        String corpId = trimToNull(environment.get("WECOM_CORP_ID"));
        String corpSecret = trimToNull(environment.get("WECOM_CORP_SECRET"));
        String agentId = trimToNull(environment.get("WECOM_AGENT_ID"));
        String toUser = trimToNull(environment.get("WECOM_TO_USER"));
        String toParty = trimToNull(environment.get("WECOM_TO_PARTY"));
        String toTag = trimToNull(environment.get("WECOM_TO_TAG"));
        if (corpId != null && corpSecret != null && agentId != null && hasAtLeastOneTarget(toUser, toParty, toTag)) {
            String apiBaseUrl = normalizeBaseUrl(trimToNull(environment.get("WECOM_API_BASE_URL")));
            return new WeComNotifier(
                    Mode.APP,
                    HttpClient.newHttpClient(),
                    new ObjectMapper(),
                    null,
                    apiBaseUrl == null ? DEFAULT_API_BASE_URL : apiBaseUrl,
                    corpId,
                    corpSecret,
                    agentId,
                    toUser,
                    toParty,
                    toTag
            );
        }

        return NotificationSender.DISABLED;
    }

    static NotificationSender requireFromEnvironment(Map<String, String> environment) {
        NotificationSender sender = fromEnvironment(environment);
        if (sender.isEnabled()) {
            return sender;
        }

        throw new IllegalStateException(
                "WeCom notification is required. Configure either "
                        + "WECOM_WEBHOOK_URL / WECOM_WEBHOOK_KEY, or "
                        + "WECOM_CORP_ID + WECOM_CORP_SECRET + WECOM_AGENT_ID + "
                        + "(WECOM_TO_USER / WECOM_TO_PARTY / WECOM_TO_TAG)."
        );
    }

    static Map<String, String> withCodeDefaults(Map<String, String> environment) {
        Objects.requireNonNull(environment, "environment");

        Map<String, String> merged = new LinkedHashMap<>();
        merged.put("WECOM_CORP_ID", DEFAULT_CORP_ID);
        merged.put("WECOM_CORP_SECRET", DEFAULT_CORP_SECRET);
        merged.put("WECOM_AGENT_ID", DEFAULT_AGENT_ID);
        merged.put("WECOM_TO_PARTY", DEFAULT_TO_PARTY);
        merged.putAll(environment);
        return merged;
    }

    @Override
    public boolean isEnabled() {
        return true;
    }

    @Override
    public void sendText(String message) {
        Objects.requireNonNull(message, "message");
        try {
            if (mode == Mode.WEBHOOK) {
                sendWebhookText(message);
            } else {
                sendAppText(message);
            }
        } catch (IOException e) {
            throw new IllegalStateException("Failed to send WeCom message", e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted while sending WeCom message", e);
        }
    }

    private void sendWebhookText(String message) throws IOException, InterruptedException {
        Map<String, Object> payload = new LinkedHashMap<>();
        payload.put("msgtype", "text");
        payload.put("text", Map.of("content", message));
        sendJsonRequest(webhookUri, payload);
    }

    private void sendAppText(String message) throws IOException, InterruptedException {
        Map<String, Object> payload = new LinkedHashMap<>();
        if (toUser != null) {
            payload.put("touser", toUser);
        }
        if (toParty != null) {
            payload.put("toparty", toParty);
        }
        if (toTag != null) {
            payload.put("totag", toTag);
        }
        payload.put("msgtype", "text");
        payload.put("agentid", Integer.parseInt(agentId));
        payload.put("text", Map.of("content", message));
        payload.put("safe", 0);

        URI messageUri = URI.create(
                apiBaseUrl + "/cgi-bin/message/send?access_token=" + urlEncode(getAccessToken())
        );
        sendJsonRequest(messageUri, payload);
    }

    private String getAccessToken() throws IOException, InterruptedException {
        AccessToken current = accessToken;
        if (current.isValid()) {
            return current.value;
        }

        synchronized (this) {
            current = accessToken;
            if (current.isValid()) {
                return current.value;
            }

            URI tokenUri = URI.create(
                    apiBaseUrl
                            + "/cgi-bin/gettoken?corpid=" + urlEncode(corpId)
                            + "&corpsecret=" + urlEncode(corpSecret)
            );
            HttpRequest request = HttpRequest.newBuilder(tokenUri)
                    .timeout(HTTP_TIMEOUT)
                    .GET()
                    .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
            JsonNode payload = parseAndValidateResponse(response, "WeCom gettoken");
            String token = payload.path("access_token").asText("");
            int expiresIn = payload.path("expires_in").asInt(7200);
            if (token.isBlank()) {
                throw new IllegalStateException("WeCom gettoken response missing access_token");
            }

            accessToken = new AccessToken(token, Instant.now().plusSeconds(Math.max(60, expiresIn - 60L)));
            return accessToken.value;
        }
    }

    private void sendJsonRequest(URI uri, Map<String, Object> payload) throws IOException, InterruptedException {
        String requestBody = objectMapper.writeValueAsString(payload);
        HttpRequest request = HttpRequest.newBuilder(uri)
                .timeout(HTTP_TIMEOUT)
                .header("Content-Type", "application/json; charset=UTF-8")
                .POST(HttpRequest.BodyPublishers.ofString(requestBody, StandardCharsets.UTF_8))
                .build();
        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString(StandardCharsets.UTF_8));
        parseAndValidateResponse(response, "WeCom send");
    }

    private JsonNode parseAndValidateResponse(HttpResponse<String> response, String action) throws IOException {
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IllegalStateException(action + " failed with HTTP status " + response.statusCode());
        }

        JsonNode payload = objectMapper.readTree(response.body());
        int errCode = payload.path("errcode").asInt(Integer.MIN_VALUE);
        if (errCode != 0) {
            throw new IllegalStateException(
                    action + " failed with errcode=" + errCode + ", errmsg=" + payload.path("errmsg").asText("")
            );
        }
        return payload;
    }

    private static String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private static String normalizeBaseUrl(String value) {
        String trimmed = trimToNull(value);
        if (trimmed == null) {
            return null;
        }
        return trimmed.endsWith("/") ? trimmed.substring(0, trimmed.length() - 1) : trimmed;
    }

    private static String urlEncode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private static boolean hasAtLeastOneTarget(String toUser, String toParty, String toTag) {
        return toUser != null || toParty != null || toTag != null;
    }

    private enum Mode {
        WEBHOOK,
        APP
    }

    private static final class AccessToken {
        private final String value;
        private final Instant expiresAt;

        private AccessToken(String value, Instant expiresAt) {
            this.value = value;
            this.expiresAt = expiresAt;
        }

        private static AccessToken expired() {
            return new AccessToken("", Instant.EPOCH);
        }

        private boolean isValid() {
            return !value.isBlank() && Instant.now().isBefore(expiresAt);
        }
    }
}
