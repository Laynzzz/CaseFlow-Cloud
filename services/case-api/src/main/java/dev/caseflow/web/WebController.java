package dev.caseflow.web;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;

/** Known browser routes share the packaged React entry point; API routes never fall through. */
@Controller
public class WebController {
    @GetMapping({"/", "/account", "/new", "/admin", "/cases/{caseId}"})
    public String index() { return "forward:/index.html"; }
}
