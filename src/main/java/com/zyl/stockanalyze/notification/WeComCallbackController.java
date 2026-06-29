package com.zyl.stockanalyze.notification;

import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping(WeComCallbackController.CALLBACK_PATH)
public final class WeComCallbackController {
    public static final String CALLBACK_PATH = "/wecom/callback";

    private final WeComCallbackConfig config;
    private final WeComCallbackCrypto crypto;

    public WeComCallbackController(WeComCallbackConfig config) {
        this.config = config;
        this.crypto = new WeComCallbackCrypto(config.getToken(), config.getEncodingAesKey(), config.getReceiveId());
    }

    @GetMapping
    public ResponseEntity<String> verify(
            @RequestParam("msg_signature") String msgSignature,
            @RequestParam("timestamp") String timestamp,
            @RequestParam("nonce") String nonce,
            @RequestParam("echostr") String encryptedEcho
    ) {
        String plainEcho = crypto.verifyUrl(msgSignature, timestamp, nonce, encryptedEcho);
        return ResponseEntity.ok()
                .contentType(MediaType.TEXT_PLAIN)
                .body(plainEcho);
    }

    @PostMapping(consumes = MediaType.APPLICATION_XML_VALUE)
    public ResponseEntity<String> receive(
            @RequestParam("msg_signature") String msgSignature,
            @RequestParam("timestamp") String timestamp,
            @RequestParam("nonce") String nonce,
            @RequestBody String requestBody
    ) {
        String plainMessage = crypto.decryptMessage(msgSignature, timestamp, nonce, requestBody);
        System.out.printf("[wecom-callback] received: %s%n", plainMessage);
        return ResponseEntity.ok()
                .contentType(MediaType.TEXT_PLAIN)
                .body("success");
    }
}
