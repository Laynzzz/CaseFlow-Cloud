import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

/** Dependency-free container probe; readiness includes the migrated database. */
public final class HealthProbe {
    public static void main(String[] args) throws Exception {
        var request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:8080/api/v1/health"))
            .timeout(Duration.ofSeconds(3)).build();
        var response = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build()
            .send(request, HttpResponse.BodyHandlers.discarding());
        if (response.statusCode() != 200) System.exit(1);
    }
}
