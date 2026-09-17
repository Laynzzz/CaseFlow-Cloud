package dev.caseflow.web;

import dev.caseflow.security.SecurityConfiguration;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.mock.web.MockServletContext;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;
import static org.mockito.Mockito.mock;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class WebSecurityTest {
    @Configuration @EnableWebSecurity @EnableWebMvc
    static class TestConfiguration {
        @Bean JwtDecoder decoder() { return mock(JwtDecoder.class); }
    }

    @Test void browserRoutesArePublicButApiUnknownRoutesAndWritesRemainProtected() throws Exception {
        try (var context = new AnnotationConfigWebApplicationContext()) {
            context.setServletContext(new MockServletContext());
            context.register(TestConfiguration.class, SecurityConfiguration.class, WebController.class);
            context.refresh();
            var mvc = MockMvcBuilders.webAppContextSetup(context).apply(springSecurity()).build();
            for (var path : new String[]{"/", "/account", "/new", "/admin", "/cases/00000000-0000-4000-8000-000000000001"}) {
                mvc.perform(get(path)).andExpect(status().isOk()).andExpect(forwardedUrl("/index.html"));
            }
            mvc.perform(get("/api/v1/me")).andExpect(status().isUnauthorized());
            mvc.perform(get("/actuator/prometheus")).andExpect(status().isUnauthorized());
            mvc.perform(get("/not-a-client-route")).andExpect(status().isUnauthorized());
            mvc.perform(post("/admin")).andExpect(status().isUnauthorized());
        }
    }
}
