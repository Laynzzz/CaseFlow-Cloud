package dev.caseflow.documents;

import java.net.URI;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class ObjectStoragePublicEndpointTest {
    @Test void browserDownloadsUsePublicEndpointAndRetainSignatureAndObjectPath() {
        try (var storage = new ObjectStorage("http://object-store:8333", "http://127.0.0.1:18333", "us-east-1", "caseflow-release", "synthetic-access", "synthetic-secret")) {
            var url = URI.create(storage.download("tenant/artifacts/approved.docx"));
            assertEquals("127.0.0.1", url.getHost());
            assertEquals(18333, url.getPort());
            assertEquals("/caseflow-release/tenant/artifacts/approved.docx", url.getPath());
            assertTrue(url.getQuery().contains("X-Amz-Signature="));
            assertTrue(url.getQuery().contains("X-Amz-Expires=60"));
        }
    }
    @Test void omittedPublicEndpointKeepsExistingLocalDownloadAddress() {
        try (var storage = new ObjectStorage("http://127.0.0.1:8333", "", "us-east-1", "caseflow-local", "synthetic-access", "synthetic-secret")) {
            assertEquals(8333, URI.create(storage.download("approved.docx")).getPort());
        }
    }
}
