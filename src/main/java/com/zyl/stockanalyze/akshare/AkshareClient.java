package com.zyl.stockanalyze.akshare;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

public final class AkshareClient {
    private static final Duration DEFAULT_TIMEOUT = Duration.ofSeconds(30);

    private final String pythonCommand;
    private final Path scriptPath;
    private final Duration timeout;
    private final ObjectMapper objectMapper;

    public AkshareClient() {
        this(resolvePythonCommand(), resolveScriptPath(), DEFAULT_TIMEOUT);
    }

    public AkshareClient(String pythonCommand, Path scriptPath, Duration timeout) {
        this.pythonCommand = Objects.requireNonNull(pythonCommand, "pythonCommand");
        this.scriptPath = Objects.requireNonNull(scriptPath, "scriptPath").toAbsolutePath().normalize();
        this.timeout = Objects.requireNonNull(timeout, "timeout");
        this.objectMapper = new ObjectMapper()
                .registerModule(new JavaTimeModule())
                .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
    }

    public AkshareResponse invoke(String function, Map<String, ?> params) {
        if (function == null || function.isBlank()) {
            throw new IllegalArgumentException("function must not be blank");
        }

        Objects.requireNonNull(params, "params");
        if (!Files.exists(scriptPath)) {
            throw new IllegalStateException("AkShare bridge script not found: " + scriptPath);
        }

        ProcessResult processResult = runProcess(function, params);
        JsonNode payload = parsePayload(function, processResult);

        if (!payload.path("success").asBoolean(false)) {
            throw new AkshareException(
                    function,
                    processResult.exitCode,
                    payload.path("errorMessage").asText("AkShare bridge invocation failed"),
                    payload,
                    processResult.output
            );
        }

        return new AkshareResponse(payload.path("function").asText(function), payload.path("data"));
    }

    private ProcessResult runProcess(String function, Map<String, ?> params) {
        final String paramsJson;
        try {
            paramsJson = objectMapper.writeValueAsString(params);
        } catch (IOException e) {
            throw new IllegalArgumentException("Failed to serialize params for AkShare", e);
        }

        List<String> command = List.of(pythonCommand, scriptPath.toString(), function, paramsJson);
        ProcessBuilder processBuilder = new ProcessBuilder(command);
        processBuilder.redirectErrorStream(true);

        ExecutorService executor = Executors.newSingleThreadExecutor();
        try {
            Process process = processBuilder.start();
            Future<String> outputFuture = executor.submit(
                    () -> new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8)
            );

            if (!process.waitFor(timeout.toMillis(), TimeUnit.MILLISECONDS)) {
                process.destroyForcibly();
                throw new AkshareException(function, -1, "AkShare bridge timed out after " + timeout, null, "");
            }

            String output = outputFuture.get(5, TimeUnit.SECONDS).trim();
            return new ProcessResult(process.exitValue(), output);
        } catch (IOException e) {
            throw new IllegalStateException("Failed to start AkShare bridge process", e);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted while waiting for AkShare bridge", e);
        } catch (ExecutionException e) {
            throw new IllegalStateException("Failed to read AkShare bridge output", e.getCause());
        } catch (TimeoutException e) {
            throw new IllegalStateException("Timed out while reading AkShare bridge output", e);
        } finally {
            executor.shutdownNow();
        }
    }

    private JsonNode parsePayload(String function, ProcessResult processResult) {
        if (processResult.output.isBlank()) {
            throw new AkshareException(function, processResult.exitCode, "AkShare bridge returned empty output", null, "");
        }

        String rawPayload = extractPayload(processResult.output);
        try {
            return objectMapper.readTree(rawPayload);
        } catch (IOException e) {
            throw new AkshareException(
                    function,
                    processResult.exitCode,
                    "Failed to parse AkShare bridge output",
                    null,
                    processResult.output
            );
        }
    }

    private String extractPayload(String output) {
        String[] lines = output.trim().split("\\R");
        for (int i = lines.length - 1; i >= 0; i--) {
            String candidate = lines[i].trim();
            if (candidate.startsWith("{") || candidate.startsWith("[")) {
                return candidate;
            }
        }
        return output.trim();
    }

    private static String resolvePythonCommand() {
        return resolvePythonCommand(System.getenv(), Path.of("").toAbsolutePath().normalize());
    }

    static String resolvePythonCommand(Map<String, String> environment, Path workingDirectory) {
        Objects.requireNonNull(environment, "environment");
        Objects.requireNonNull(workingDirectory, "workingDirectory");

        String override = environment.get("AKSHARE_PYTHON");
        if (override != null && !override.isBlank()) {
            return override;
        }

        Path normalizedWorkingDirectory = workingDirectory.toAbsolutePath().normalize();
        List<Path> localVenvCandidates = List.of(
                normalizedWorkingDirectory.resolve(".venv").resolve("bin").resolve("python"),
                normalizedWorkingDirectory.resolve(".venv").resolve("bin").resolve("python3"),
                normalizedWorkingDirectory.resolve(".venv").resolve("Scripts").resolve("python.exe"),
                normalizedWorkingDirectory.resolve(".venv").resolve("Scripts").resolve("python")
        );

        for (Path candidate : localVenvCandidates) {
            if (Files.isRegularFile(candidate) && Files.isExecutable(candidate)) {
                return candidate.toString();
            }
        }

        return "python3";
    }

    private static Path resolveScriptPath() {
        String override = System.getenv("AKSHARE_BRIDGE_SCRIPT");
        if (override != null && !override.isBlank()) {
            return Path.of(override);
        }
        return Path.of("scripts", "akshare_bridge.py");
    }

    private static final class ProcessResult {
        private final int exitCode;
        private final String output;

        private ProcessResult(int exitCode, String output) {
            this.exitCode = exitCode;
            this.output = output;
        }
    }
}
