package dev.caseflow.observability;

import dev.caseflow.security.SecurityConfiguration;
import org.junit.jupiter.api.Test;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.mock.web.MockServletContext;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.context.support.AnnotationConfigWebApplicationContext;
import org.springframework.web.servlet.config.annotation.EnableWebMvc;
import static org.mockito.Mockito.mock;
import static org.springframework.security.test.web.servlet.setup.SecurityMockMvcConfigurers.springSecurity;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class ManagementSecurityTest {
    @Configuration @EnableWebSecurity @EnableWebMvc
    static class TestConfig {
        @Bean JwtDecoder decoder() {return mock(JwtDecoder.class);}
    }
    @RestController static class Endpoints {
        @GetMapping("/actuator/prometheus") String metrics() {return "metric 1";}
    }
    @Test void onlyPrivateListenerCanReadExplicitOperationalEndpoints() throws Exception {
        try(var context=new AnnotationConfigWebApplicationContext()) {
            context.setServletContext(new MockServletContext());
            context.register(TestConfig.class,Endpoints.class,SecurityConfiguration.class,ManagementSecurity.class);
            context.refresh();
            var mvc=MockMvcBuilders.webAppContextSetup(context).apply(springSecurity()).build();
            mvc.perform(get("/actuator/prometheus").with(r->{r.setLocalPort(9091);return r;})).andExpect(status().isOk());
            mvc.perform(get("/actuator/prometheus").header("X-Forwarded-Port","9091").with(r->{r.setLocalPort(8080);return r;})).andExpect(status().isUnauthorized());
            mvc.perform(get("/actuator/env").with(r->{r.setLocalPort(9091);return r;})).andExpect(status().isForbidden());
            mvc.perform(post("/actuator/prometheus").with(r->{r.setLocalPort(9091);return r;})).andExpect(status().isForbidden());
        }
    }
}
