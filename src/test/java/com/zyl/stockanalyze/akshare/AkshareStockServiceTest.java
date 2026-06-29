//package com.zyl.stockanalyze.akshare;
//
//import org.junit.jupiter.api.Test;
//
//import java.nio.file.Path;
//import java.time.Duration;
//
//import static org.junit.jupiter.api.Assertions.assertEquals;
//
//class AkshareStockServiceTest {
//    private final AkshareStockService service = new AkshareStockService(new AkshareClient(
//            "python3",
//            Path.of("src", "test", "resources", "fake_akshare_bridge.py").toAbsolutePath(),
//            Duration.ofSeconds(5)
//    ));
//
//    @Test
//    void shouldResolveStockNameFromCodeNameTable() {
//        assertEquals("贵州茅台", service.getStockName("600519"));
//    }
//
//    @Test
//    void shouldFallbackToSymbolWhenNameMissing() {
//        assertEquals("999999", service.getStockName("999999"));
//    }
//}
