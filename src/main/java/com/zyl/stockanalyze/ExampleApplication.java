package com.zyl.stockanalyze;

import com.zyl.stockanalyze.akshare.AkshareClient;
import com.zyl.stockanalyze.akshare.AkshareStockService;
import com.zyl.stockanalyze.notification.NotificationSender;
import com.zyl.stockanalyze.notification.WeComCallbackConfig;
import com.zyl.stockanalyze.notification.WeComNotifier;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class ExampleApplication {
    public static void main(String[] args) {
        SpringApplication.run(ExampleApplication.class, args);
    }

    @Bean
    AkshareClient akshareClient() {
        return new AkshareClient();
    }

    @Bean
    AkshareStockService akshareStockService(AkshareClient akshareClient) {
        return new AkshareStockService(akshareClient);
    }

    @Bean
    NotificationSender notificationSender() {
        return WeComNotifier.requireFromEnvironment();
    }

    @Bean
    WeComCallbackConfig weComCallbackConfig(
            @Value("${wecom.callback.receive-id}") String receiveId,
            @Value("${wecom.callback.token}") String token,
            @Value("${wecom.callback.encoding-aes-key}") String encodingAesKey
    ) {
        return WeComCallbackConfig.fromProperties(receiveId, token, encodingAesKey);
    }
}
