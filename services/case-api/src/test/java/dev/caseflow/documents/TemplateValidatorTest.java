package dev.caseflow.documents;

import dev.caseflow.common.Problem;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.zip.*;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class TemplateValidatorTest {
    private final TemplateValidator validator=new TemplateValidator();
    private byte[] docx(String body,String relationship) throws Exception {
        var output=new ByteArrayOutputStream();
        try(var zip=new ZipOutputStream(output)) {
            for(var entry:java.util.Map.of("[Content_Types].xml","<Types/>","_rels/.rels",relationship,
                "word/document.xml","<document><p>"+body+"</p></document>").entrySet()) {
                zip.putNextEntry(new ZipEntry(entry.getKey()));zip.write(entry.getValue().getBytes(StandardCharsets.UTF_8));zip.closeEntry();
            }
        }
        return output.toByteArray();
    }
    @Test void acceptsAllowlistedPlaceholders() throws Exception {
        assertDoesNotThrow(()->validator.validate(docx("{{ vendor }} {{ total }}","<Relationships/>")));
    }
    @Test void rejectsExpressionsAndStatements() throws Exception {
        for(String input:new String[]{"{{ vendor.__class__ }}","{% for x in vendor %}","{{ secret }}","{{ vendor|safe }}"})
            assertThrows(Problem.class,()->validator.validate(docx(input,"<Relationships/>")));
    }
    @Test void rejectsExternalRelationshipsAndSplitTokens() {
        assertThrows(Problem.class,()->validator.validate(docx("{{ vendor }}","<Relationships><Relationship TargetMode=\"External\" Target=\"https://example.invalid\"/></Relationships>")));
        assertThrows(Problem.class,()->validator.validate(docx("<r>{{ ven</r><r>dor }}</r>","<Relationships/>")));
    }
    @Test void rejectsInvalidArchivesAndEntityDefinitions() {
        assertThrows(Problem.class,()->validator.validate("not a zip".getBytes(StandardCharsets.UTF_8)));
        assertThrows(Problem.class,()->validator.validate(docx("{{ vendor }}","<!DOCTYPE r [<!ENTITY x SYSTEM 'file:///never-read'>]><Relationships>&x;</Relationships>")));
    }
}
