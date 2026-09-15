package dev.caseflow.common;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.springframework.stereotype.Component;
import tools.jackson.databind.ObjectMapper;
import tools.jackson.core.type.TypeReference;

@Component
public class Json {
    private final ObjectMapper mapper;
    public Json(ObjectMapper mapper) { this.mapper = mapper; }
    public String write(Object value) { return mapper.writeValueAsString(value); }
    public Map<String,Object> object(String value) { return mapper.readValue(value, new TypeReference<>() {}); }
    public List<Object> list(String value) { return mapper.readValue(value, new TypeReference<>() {}); }
    public <T> T convert(Object value, Class<T> type) { return mapper.convertValue(value, type); }
    private Object sorted(Object value) {
        if (value instanceof Map<?,?> map) {
            var result = new TreeMap<String,Object>();
            map.forEach((k,v) -> result.put(k.toString(), sorted(v))); return result;
        }
        if (value instanceof List<?> list) return list.stream().map(this::sorted).toList();
        return value;
    }
    public String hash(Object value) {
        try {
            var canonical = write(sorted(mapper.convertValue(value, Object.class)));
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(canonical.getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException impossible) { throw new IllegalStateException(impossible); }
    }
}
