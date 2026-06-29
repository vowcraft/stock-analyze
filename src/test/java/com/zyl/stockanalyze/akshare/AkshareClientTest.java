//package com.zyl.stockanalyze.akshare;
//
//import org.junit.jupiter.api.Test;
//import org.junit.jupiter.api.io.TempDir;
//
//import java.nio.file.Path;
//import java.time.Duration;
//import java.util.HashMap;
//import java.util.Map;
//
//import static org.junit.jupiter.api.Assertions.assertEquals;
//import static org.junit.jupiter.api.Assertions.assertThrows;
//import static org.junit.jupiter.api.Assertions.assertTrue;
//
//class AkshareClientTest {
//    private final AkshareClient client = new AkshareClient(
//            "python3",
//            Path.of("src", "test", "resources", "fake_akshare_bridge.py").toAbsolutePath(),
//            Duration.ofSeconds(5)
//    );
//
//    @Test
//    void shouldInvokeBridgeAndParsePayload() {
//        AkshareResponse response = client.invoke("stock_zh_a_hist", Map.of("symbol", "600519", "period", "daily"));
//
//        assertEquals("stock_zh_a_hist", response.getFunction());
//        assertTrue(response.getData().isArray());
//        assertEquals("600519", response.getData().get(0).path("symbol").asText());
//        assertEquals("daily", response.getData().get(0).path("period").asText());
//    }
//
//    @Test
//    void shouldSurfaceBridgeFailures() {
//        AkshareException exception = assertThrows(AkshareException.class, () -> client.invoke("explode", Map.of()));
//
//        assertEquals("explode", exception.getFunction());
//        assertEquals(1, exception.getExitCode());
//        assertTrue(exception.getMessage().contains("boom"));
//    }
//
//    @Test
//    void shouldPreferLocalVirtualEnvPythonWhenPresent(@TempDir Path tempDir) throws Exception {
//        Path localPython = tempDir.resolve(".venv").resolve("bin").resolve("python");
//        java.nio.file.Files.createDirectories(localPython.getParent());
//        java.nio.file.Files.writeString(localPython, "#!/bin/sh\n");
//        assertTrue(localPython.toFile().setExecutable(true));
//
//        String resolved = AkshareClient.resolvePythonCommand(Map.of(), tempDir);
//
//        assertEquals(localPython.toString(), resolved);
//    }
//
//    @Test
//    void shouldPreferEnvironmentOverrideOverLocalVirtualEnv(@TempDir Path tempDir) throws Exception {
//        Path localPython = tempDir.resolve(".venv").resolve("bin").resolve("python");
//        java.nio.file.Files.createDirectories(localPython.getParent());
//        java.nio.file.Files.writeString(localPython, "#!/bin/sh\n");
//        assertTrue(localPython.toFile().setExecutable(true));
//
//        Map<String, String> environment = new HashMap<>();
//        environment.put("AKSHARE_PYTHON", "/custom/python");
//
//        String resolved = AkshareClient.resolvePythonCommand(environment, tempDir);
//
//        assertEquals("/custom/python", resolved);
//    }
//}
