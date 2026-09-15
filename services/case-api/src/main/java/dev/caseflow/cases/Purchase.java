package dev.caseflow.cases;

import dev.caseflow.common.Problem;
import java.math.*;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;

public record Purchase(@NotNull @Size(max=200) String vendor,
                       @NotNull @Size(max=2000) String description,
                       @NotNull @Pattern(regexp="[A-Z]{3}") String currency,
                       @NotNull @Size(max=100) String costCenter,
                       @NotNull @Size(max=4000) String justification,
                       @NotNull @Size(max=100) List<@Valid Item> lineItems) {
    public record Item(@NotNull @Size(max=500) String description,
                       @NotNull @DecimalMin(value="0",inclusive=false) @Digits(integer=8,fraction=3) BigDecimal quantity,
                       @NotNull @DecimalMin("0") @Digits(integer=12,fraction=4) BigDecimal unitPrice) {}
    public Map<String,Object> normalized(boolean complete) {
        int decimals;
        try { decimals=Currency.getInstance(currency).getDefaultFractionDigits(); }
        catch(IllegalArgumentException e) { throw new Problem(400,"Unsupported ISO currency"); }
        Problem.require(decimals>=0 && decimals<=4,"Unsupported currency precision");
        if(complete) {
            Problem.require(!vendor.isBlank() && !description.isBlank() && !costCenter.isBlank()
                    && !justification.isBlank() && !lineItems.isEmpty(),"Complete vendor, description, cost center, justification and line items before submission");
        }
        BigDecimal total=BigDecimal.ZERO.setScale(decimals);
        var lines=new ArrayList<Map<String,Object>>();
        for(var item:lineItems) {
            Problem.require(item.unitPrice().stripTrailingZeros().scale()<=decimals,"Unit price has too many decimal places for the currency");
            if(complete) Problem.require(!item.description().isBlank(),"Each line item needs a description");
            total=total.add(item.quantity().multiply(item.unitPrice()).setScale(decimals,RoundingMode.HALF_UP));
            lines.add(Map.of("description",item.description().trim(),"quantity",item.quantity().toPlainString(),"unitPrice",item.unitPrice().setScale(decimals).toPlainString()));
        }
        Problem.require(total.precision()<=16,"Purchase total is too large");
        return Map.of("vendor",vendor.trim(),"description",description.trim(),"currency",currency,
                "costCenter",costCenter.trim(),"justification",justification.trim(),"lineItems",lines,"total",total.toPlainString());
    }
}
