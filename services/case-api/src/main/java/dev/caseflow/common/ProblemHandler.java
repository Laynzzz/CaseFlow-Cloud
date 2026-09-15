package dev.caseflow.common;

import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.dao.TransientDataAccessException;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

@RestControllerAdvice
public class ProblemHandler {
    @ExceptionHandler(Problem.class)
    ResponseEntity<ProblemDetail> problem(Problem error) {
        var detail = ProblemDetail.forStatusAndDetail(org.springframework.http.HttpStatusCode.valueOf(error.status), error.getMessage());
        detail.setProperty("retryable", error.retryable);
        return ResponseEntity.status(error.status).body(detail);
    }
    @ExceptionHandler({MethodArgumentNotValidException.class, HttpMessageNotReadableException.class,
            MethodArgumentTypeMismatchException.class, IllegalArgumentException.class})
    ResponseEntity<ProblemDetail> validation(Exception error) {
        return problem(new Problem(400, "Invalid request. Check the supplied fields."));
    }
    @ExceptionHandler(DataIntegrityViolationException.class)
    ResponseEntity<ProblemDetail> constraint(DataIntegrityViolationException error) {
        return problem(new Problem(409, "The request conflicts with an existing record or business rule."));
    }
    @ExceptionHandler(TransientDataAccessException.class)
    ResponseEntity<ProblemDetail> transientFailure(TransientDataAccessException error) {
        return problem(new Problem(503, "The service is temporarily unavailable. Try again.", true));
    }
}
