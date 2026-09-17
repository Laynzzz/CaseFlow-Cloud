package dev.caseflow.observability;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.web.SecurityFilterChain;

/** Operational endpoints are reachable only on the separate private listener. */
@Configuration
public class ManagementSecurity {
    @Bean @Order(0)
    SecurityFilterChain managementSecurityFilterChain(HttpSecurity http,
            @Value("${management.server.port:9091}") int port,
            @Value("${server.port:8080}") int publicPort) throws Exception {
        if(port==publicPort)throw new IllegalArgumentException("Management requires a separate private port");
        return http.securityMatcher(request -> request.getLocalPort()==port && request.getRequestURI().startsWith("/actuator/"))
            .authorizeHttpRequests(auth -> auth.requestMatchers(HttpMethod.GET,"/actuator/health","/actuator/prometheus").permitAll()
                .anyRequest().denyAll())
            .csrf(csrf -> csrf.disable())
            .sessionManagement(session -> session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .formLogin(form -> form.disable()).httpBasic(basic -> basic.disable()).build();
    }
}
