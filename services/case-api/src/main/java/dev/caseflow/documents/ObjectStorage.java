package dev.caseflow.documents;

import dev.caseflow.common.Problem;
import java.io.IOException;
import java.net.URI;
import java.security.MessageDigest;
import java.time.Duration;
import java.util.HexFormat;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import software.amazon.awssdk.auth.credentials.*;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.S3Configuration;
import software.amazon.awssdk.services.s3.model.*;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;

@Component
public class ObjectStorage implements AutoCloseable {
    public static final int MAX_BYTES = 10 * 1024 * 1024;
    public static final String DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    private final S3Client client;
    private final S3Presigner signer;
    private final String bucket;

    public ObjectStorage(@Value("${caseflow.storage.endpoint:http://127.0.0.1:8333}") String endpoint,
                         @Value("${caseflow.storage.region:us-east-1}") String region,
                         @Value("${caseflow.storage.bucket:caseflow-local}") String bucket,
                         @Value("${S3_ACCESS_KEY:}") String accessKey,
                         @Value("${S3_SECRET_KEY:}") String secretKey) {
        this.bucket = bucket;
        AwsCredentialsProvider credentials = endpoint.isBlank()
            ? DefaultCredentialsProvider.builder().build()
            : StaticCredentialsProvider.create(AwsBasicCredentials.create(accessKey, secretKey));
        var configuration = S3Configuration.builder().pathStyleAccessEnabled(!endpoint.isBlank())
            .chunkedEncodingEnabled(false).build();
        var builder = S3Client.builder().region(Region.of(region)).credentialsProvider(credentials)
            .serviceConfiguration(configuration)
            .httpClientBuilder(UrlConnectionHttpClient.builder().connectionTimeout(Duration.ofSeconds(3)).socketTimeout(Duration.ofSeconds(15)))
            .overrideConfiguration(c -> c.apiCallTimeout(Duration.ofSeconds(25)));
        var presigner = S3Presigner.builder().region(Region.of(region)).credentialsProvider(credentials)
            .serviceConfiguration(configuration);
        if (!endpoint.isBlank()) { builder.endpointOverride(URI.create(endpoint)); presigner.endpointOverride(URI.create(endpoint)); }
        client = builder.build(); signer = presigner.build();
    }

    public void put(String key, byte[] bytes, boolean immutable) {
        put(key,bytes,immutable,DOCX);
    }
    public void put(String key, byte[] bytes, boolean immutable, String mediaType) {
        var request = PutObjectRequest.builder().bucket(bucket).key(key).contentType(mediaType)
            .checksumSHA256(java.util.Base64.getEncoder().encodeToString(HexFormat.of().parseHex(checksum(bytes))));
        if (immutable) request.ifNoneMatch("*");
        client.putObject(request.build(), RequestBody.fromBytes(bytes));
    }

    public byte[] read(String key) {
        try (var input = client.getObject(GetObjectRequest.builder().bucket(bucket).key(key).build())) {
            if (input.response().contentLength() > MAX_BYTES) throw new Problem(400,"File exceeds the 10 MB limit");
            byte[] bytes = input.readNBytes(MAX_BYTES + 1);
            Problem.require(bytes.length <= MAX_BYTES, "File exceeds the 10 MB limit");
            return bytes;
        } catch (NoSuchKeyException e) { throw new Problem(400,"Upload the file before finalizing it"); }
        catch (IOException e) { throw new Problem(503,"Object storage is unavailable",true); }
    }

    public String download(String key) {
        return signer.presignGetObject(p -> p.signatureDuration(Duration.ofSeconds(60))
            .getObjectRequest(r -> r.bucket(bucket).key(key).responseContentType(DOCX)
                .responseContentDisposition("attachment; filename=approved-purchase.docx"))).url().toString();
    }

    public static String checksum(byte[] bytes) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); }
        catch (java.security.NoSuchAlgorithmException e) { throw new IllegalStateException(e); }
    }
    @Override public void close() { client.close(); signer.close(); }
}
