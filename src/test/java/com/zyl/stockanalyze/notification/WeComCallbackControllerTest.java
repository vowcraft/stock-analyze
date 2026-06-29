package com.zyl.stockanalyze.notification;

import com.zyl.stockanalyze.ExampleApplication;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.content;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@SpringBootTest(
        classes = ExampleApplication.class,
        webEnvironment = SpringBootTest.WebEnvironment.MOCK
)
@AutoConfigureMockMvc
@TestPropertySource(properties = {
        "app.polling.enabled=false",
        "app.symbol=600519",
        "wecom.callback.receive-id=ww-test-corp",
        "wecom.callback.token=test-token",
        "wecom.callback.encoding-aes-key=yDJGijqy+YHErEFLuf5g2e/zIcxu7azZN16kJT3rkds"
})
class WeComCallbackControllerTest {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private WeComCallbackConfig config;

    @Test
    void shouldVerifyCallbackUrl() throws Exception {
        WeComCallbackCrypto crypto = new WeComCallbackCrypto(
                config.getToken(),
                config.getEncodingAesKey(),
                config.getReceiveId()
        );
        String timestamp = "1719650000";
        String nonce = "nonce-verify";
        String encryptedEcho = crypto.encrypt("callback-ok");
        String signature = crypto.sign(timestamp, nonce, encryptedEcho);

        mockMvc.perform(get(WeComCallbackController.CALLBACK_PATH)
                        .queryParam("msg_signature", signature)
                        .queryParam("timestamp", timestamp)
                        .queryParam("nonce", nonce)
                        .queryParam("echostr", encryptedEcho))
                .andExpect(status().isOk())
                .andExpect(content().string("callback-ok"));
    }

    @Test
    void shouldReceiveAndDecryptCallbackMessage() throws Exception {
        WeComCallbackCrypto crypto = new WeComCallbackCrypto(
                config.getToken(),
                config.getEncodingAesKey(),
                config.getReceiveId()
        );
        String plainMessage = "<xml><MsgType><![CDATA[event]]></MsgType><Event><![CDATA[enter_agent]]></Event></xml>";
        String timestamp = "1719650001";
        String nonce = "nonce-message";
        String encrypted = crypto.encrypt(plainMessage);
        String signature = crypto.sign(timestamp, nonce, encrypted);
        String body = "<xml><Encrypt><![CDATA[" + encrypted + "]]></Encrypt></xml>";

        mockMvc.perform(post(WeComCallbackController.CALLBACK_PATH)
                        .queryParam("msg_signature", signature)
                        .queryParam("timestamp", timestamp)
                        .queryParam("nonce", nonce)
                        .contentType("application/xml")
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(content().string("success"));
    }
}
