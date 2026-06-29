package com.zyl.stockanalyze.notification;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Objects;

public final class WeComCallbackConfig {
    private static final String DEFAULT_CALLBACK_TOKEN = "stockanalyze2026";
    private static final String DEFAULT_CALLBACK_ENCODING_AES_KEY = "stockanalyze2026abcdefghijklmnopqrstuvwxyz1";

    private final String receiveId;
    private final String token;
    private final String encodingAesKey;

    private WeComCallbackConfig(String receiveId, String token, String encodingAesKey) {
        this.receiveId = receiveId;
        this.token = token;
        this.encodingAesKey = encodingAesKey;
    }

    public static WeComCallbackConfig fromEnvironment() {
        return fromEnvironment(System.getenv());
    }

    public static WeComCallbackConfig fromProperties(
            String receiveId,
            String token,
            String encodingAesKey
    ) {
        String resolvedReceiveId = trimToNull(receiveId);
        String resolvedToken = trimToNull(token);
        String resolvedEncodingAesKey = trimToNull(encodingAesKey);

        if (resolvedReceiveId == null) {
            throw new IllegalStateException("WECOM_CALLBACK_RECEIVE_ID or WECOM_CORP_ID must be configured");
        }
        if (resolvedToken == null) {
            throw new IllegalStateException("WECOM_CALLBACK_TOKEN must be configured");
        }
        requireEnglishOrDigits("WECOM_CALLBACK_TOKEN", resolvedToken);
        if (resolvedEncodingAesKey == null || resolvedEncodingAesKey.length() != 43) {
            throw new IllegalStateException("WECOM_CALLBACK_ENCODING_AES_KEY must be a 43-character string");
        }
        requireEnglishOrDigits("WECOM_CALLBACK_ENCODING_AES_KEY", resolvedEncodingAesKey);

        return new WeComCallbackConfig(resolvedReceiveId, resolvedToken, resolvedEncodingAesKey);
    }

    static WeComCallbackConfig fromEnvironment(Map<String, String> environment) {
        Objects.requireNonNull(environment, "environment");

        Map<String, String> merged = new LinkedHashMap<>(WeComNotifier.withCodeDefaults(environment));
        merged.putIfAbsent("WECOM_CALLBACK_TOKEN", DEFAULT_CALLBACK_TOKEN);
        merged.putIfAbsent("WECOM_CALLBACK_ENCODING_AES_KEY", DEFAULT_CALLBACK_ENCODING_AES_KEY);

        String receiveId = trimToNull(merged.get("WECOM_CALLBACK_RECEIVE_ID"));
        if (receiveId == null) {
            receiveId = trimToNull(merged.get("WECOM_CORP_ID"));
        }
        String token = trimToNull(merged.get("WECOM_CALLBACK_TOKEN"));
        String encodingAesKey = trimToNull(merged.get("WECOM_CALLBACK_ENCODING_AES_KEY"));

        return fromProperties(receiveId, token, encodingAesKey);
    }

    public String getReceiveId() {
        return receiveId;
    }

    public String getToken() {
        return token;
    }

    public String getEncodingAesKey() {
        return encodingAesKey;
    }

    private static String trimToNull(String value) {
        if (value == null) {
            return null;
        }
        String trimmed = value.trim();
        return trimmed.isEmpty() ? null : trimmed;
    }

    private static void requireEnglishOrDigits(String name, String value) {
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            if (!(c >= '0' && c <= '9') && !(c >= 'A' && c <= 'Z') && !(c >= 'a' && c <= 'z')) {
                throw new IllegalStateException(name + " must contain only English letters or digits");
            }
        }
    }
}
