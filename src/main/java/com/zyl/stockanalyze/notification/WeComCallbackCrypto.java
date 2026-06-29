package com.zyl.stockanalyze.notification;

import org.w3c.dom.Document;
import org.xml.sax.InputSource;

import javax.crypto.Cipher;
import javax.crypto.spec.IvParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.StringReader;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;
import java.util.Objects;

public final class WeComCallbackCrypto {
    private static final int BLOCK_SIZE = 32;

    private final String token;
    private final byte[] aesKey;
    private final byte[] iv;
    private final String receiveId;
    private final SecureRandom secureRandom;

    public WeComCallbackCrypto(String token, String encodingAesKey, String receiveId) {
        this(token, encodingAesKey, receiveId, new SecureRandom());
    }

    WeComCallbackCrypto(String token, String encodingAesKey, String receiveId, SecureRandom secureRandom) {
        this.token = Objects.requireNonNull(token, "token");
        this.receiveId = Objects.requireNonNull(receiveId, "receiveId");
        this.secureRandom = Objects.requireNonNull(secureRandom, "secureRandom");
        this.aesKey = Base64.getDecoder().decode(Objects.requireNonNull(encodingAesKey, "encodingAesKey") + "=");
        this.iv = Arrays.copyOf(this.aesKey, 16);
    }

    public String verifyUrl(String msgSignature, String timestamp, String nonce, String encryptedEcho) {
        verifySignature(msgSignature, timestamp, nonce, encryptedEcho);
        return decrypt(encryptedEcho);
    }

    public String decryptMessage(String msgSignature, String timestamp, String nonce, String requestBody) {
        String encrypted = extractXmlValue(requestBody, "Encrypt");
        verifySignature(msgSignature, timestamp, nonce, encrypted);
        return decrypt(encrypted);
    }

    public String encrypt(String plainText) {
        Objects.requireNonNull(plainText, "plainText");
        try {
            byte[] random16 = new byte[16];
            secureRandom.nextBytes(random16);
            byte[] message = plainText.getBytes(StandardCharsets.UTF_8);
            byte[] receiveIdBytes = receiveId.getBytes(StandardCharsets.UTF_8);

            ByteBuffer buffer = ByteBuffer.allocate(20 + message.length + receiveIdBytes.length);
            buffer.put(random16);
            buffer.putInt(message.length);
            buffer.put(message);
            buffer.put(receiveIdBytes);

            byte[] padded = pkcs7Pad(buffer.array());
            Cipher cipher = Cipher.getInstance("AES/CBC/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, new SecretKeySpec(aesKey, "AES"), new IvParameterSpec(iv));
            return Base64.getEncoder().encodeToString(cipher.doFinal(padded));
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("Failed to encrypt WeCom callback payload", e);
        }
    }

    public String sign(String timestamp, String nonce, String payload) {
        return sha1(token, timestamp, nonce, payload);
    }

    private void verifySignature(String msgSignature, String timestamp, String nonce, String payload) {
        if (!sha1(token, timestamp, nonce, payload).equals(msgSignature)) {
            throw new IllegalStateException("WeCom callback signature verification failed");
        }
    }

    private String decrypt(String encrypted) {
        try {
            byte[] encryptedBytes = Base64.getDecoder().decode(encrypted);
            Cipher cipher = Cipher.getInstance("AES/CBC/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, new SecretKeySpec(aesKey, "AES"), new IvParameterSpec(iv));
            byte[] original = pkcs7Unpad(cipher.doFinal(encryptedBytes));
            if (original.length < 20) {
                throw new IllegalStateException("WeCom callback payload is too short");
            }

            int xmlLength = ByteBuffer.wrap(original, 16, 4).getInt();
            int xmlStart = 20;
            int xmlEnd = xmlStart + xmlLength;
            if (xmlLength < 0 || xmlEnd > original.length) {
                throw new IllegalStateException("WeCom callback payload length is invalid");
            }

            String message = new String(original, xmlStart, xmlLength, StandardCharsets.UTF_8);
            String actualReceiveId = new String(original, xmlEnd, original.length - xmlEnd, StandardCharsets.UTF_8);
            if (!receiveId.equals(actualReceiveId)) {
                throw new IllegalStateException("WeCom callback receiveId mismatch");
            }
            return message;
        } catch (IllegalArgumentException | GeneralSecurityException e) {
            throw new IllegalStateException("Failed to decrypt WeCom callback payload", e);
        }
    }

    private static String extractXmlValue(String xml, String tagName) {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
            factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
            factory.setExpandEntityReferences(false);
            factory.setXIncludeAware(false);
            DocumentBuilder builder = factory.newDocumentBuilder();
            Document document = builder.parse(new InputSource(new StringReader(xml)));
            String value = document.getElementsByTagName(tagName).item(0).getTextContent();
            if (value == null || value.isBlank()) {
                throw new IllegalStateException("WeCom callback XML missing " + tagName);
            }
            return value.trim();
        } catch (Exception e) {
            throw new IllegalStateException("Failed to parse WeCom callback XML", e);
        }
    }

    private static byte[] pkcs7Pad(byte[] input) {
        int amountToPad = BLOCK_SIZE - (input.length % BLOCK_SIZE);
        if (amountToPad == 0) {
            amountToPad = BLOCK_SIZE;
        }
        byte[] padded = Arrays.copyOf(input, input.length + amountToPad);
        Arrays.fill(padded, input.length, padded.length, (byte) amountToPad);
        return padded;
    }

    private static byte[] pkcs7Unpad(byte[] input) {
        if (input.length == 0) {
            throw new IllegalStateException("WeCom callback payload is empty");
        }

        int pad = input[input.length - 1] & 0xFF;
        if (pad < 1 || pad > BLOCK_SIZE || pad > input.length) {
            throw new IllegalStateException("WeCom callback PKCS7 padding is invalid");
        }

        for (int i = input.length - pad; i < input.length; i++) {
            if ((input[i] & 0xFF) != pad) {
                throw new IllegalStateException("WeCom callback PKCS7 padding is invalid");
            }
        }

        return Arrays.copyOf(input, input.length - pad);
    }

    private static String sha1(String token, String timestamp, String nonce, String payload) {
        try {
            String[] parts = {token, timestamp, nonce, payload};
            Arrays.sort(parts);
            String joined = String.join("", parts);
            MessageDigest digest = MessageDigest.getInstance("SHA-1");
            byte[] hash = digest.digest(joined.getBytes(StandardCharsets.UTF_8));
            StringBuilder builder = new StringBuilder(hash.length * 2);
            for (byte b : hash) {
                builder.append(String.format("%02x", b));
            }
            return builder.toString();
        } catch (GeneralSecurityException e) {
            throw new IllegalStateException("Failed to calculate WeCom callback signature", e);
        }
    }
}
