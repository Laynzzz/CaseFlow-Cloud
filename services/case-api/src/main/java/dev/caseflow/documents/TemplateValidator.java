package dev.caseflow.documents;

import dev.caseflow.common.Problem;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.regex.Pattern;
import java.util.zip.ZipInputStream;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilderFactory;
import org.springframework.stereotype.Component;

@Component
public class TemplateValidator {
    private static final Set<String> FIELDS = Set.of("vendor","description","currency","total",
        "cost_center","justification","line_items","approved_at","case_id","approvers");
    private static final Pattern PLACEHOLDER = Pattern.compile("\\{\\{\\s*([a-z_]+)\\s*}}");

    public void validate(byte[] bytes) {
        Problem.require(bytes.length>0 && bytes.length<=ObjectStorage.MAX_BYTES,"Invalid template size");
        Set<String> entries = new HashSet<>(); int expanded=0;
        try (var zip = new ZipInputStream(new ByteArrayInputStream(bytes))) {
            for (var entry=zip.getNextEntry(); entry!=null; entry=zip.getNextEntry()) {
                String name=entry.getName();
                Problem.require(entries.add(name) && entries.size()<=500,"Invalid template archive");
                Problem.require(!name.startsWith("/") && !name.contains("..") && !name.contains("\\"),"Invalid archive path");
                Problem.require(!name.toLowerCase(Locale.ROOT).contains("vbaproject") && !name.contains("embeddings/"),"Macros and embedded objects are unsupported");
                byte[] content=zip.readNBytes(ObjectStorage.MAX_BYTES+1);
                expanded+=content.length;
                Problem.require(content.length<=ObjectStorage.MAX_BYTES && expanded<=25*1024*1024,"Expanded template is too large");
                if (entry.getCompressedSize()>0) Problem.require(content.length<=Math.max(65536,entry.getCompressedSize()*100),"Excessive archive compression");
                if (name.endsWith(".xml") || name.endsWith(".rels")) validateXml(content,name);
            }
            Problem.require(entries.contains("[Content_Types].xml") && entries.contains("word/document.xml")
                && entries.contains("_rels/.rels"),"Upload a valid DOCX template");
        } catch (Problem e) { throw e; }
        catch (Exception e) { throw new Problem(400,"Malformed or unsupported DOCX template"); }
    }

    private void validateXml(byte[] bytes,String name) throws Exception {
        var factory=DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
        factory.setFeature("http://xml.org/sax/features/external-general-entities",false);
        factory.setFeature("http://xml.org/sax/features/external-parameter-entities",false);
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_DTD,"");
        factory.setAttribute(XMLConstants.ACCESS_EXTERNAL_SCHEMA,"");
        factory.setXIncludeAware(false); factory.setExpandEntityReferences(false);
        var document=factory.newDocumentBuilder().parse(new ByteArrayInputStream(bytes));
        var relationships=document.getElementsByTagName("Relationship");
        for(int i=0;i<relationships.getLength();i++) {
            var relation=(org.w3c.dom.Element)relationships.item(i);
            Problem.require(!"External".equalsIgnoreCase(relation.getAttribute("TargetMode")),"External template relationships are unsupported");
        }
        String raw=new String(bytes,StandardCharsets.UTF_8);
        Problem.require(!raw.contains("macroEnabled") && !raw.contains("altChunk"),"Unsupported Word content");
        if (name.startsWith("word/")) {
            String text=document.getDocumentElement().getTextContent();
            Problem.require(!text.contains("{%") && !text.contains("{#"),"Template statements are unsupported");
            var matcher=PLACEHOLDER.matcher(text);
            while(matcher.find()) Problem.require(FIELDS.contains(matcher.group(1)),"Unknown template placeholder");
            String remainder=matcher.replaceAll("");
            Problem.require(!remainder.contains("{{") && !remainder.contains("}}"),"Use plain supported placeholders only");
            // Docxtpl requires a placeholder within one run. Reject markup-split tokens.
            Problem.require(PLACEHOLDER.matcher(raw).results().count()==PLACEHOLDER.matcher(text).results().count(),"Keep each placeholder in a single Word text run");
        }
    }
}
