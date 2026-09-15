package dev.caseflow.cases;

import dev.caseflow.common.Problem;
import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class PurchaseTest {
    private Purchase purchase(String currency,String quantity,String price) {
        return new Purchase("Vendor","Equipment",currency,"OPS","Required for work",
                List.of(new Purchase.Item("Item",new BigDecimal(quantity),new BigDecimal(price))));
    }
    @Test void calculatesWithDecimalArithmetic() {
        assertEquals("0.30",purchase("USD","3","0.10").normalized(true).get("total"));
    }
    @Test void roundsEachLineToCurrencyMinorUnits() {
        assertEquals("1.01",purchase("USD","0.5","2.01").normalized(true).get("total"));
        assertEquals("101",purchase("JPY","0.5","201").normalized(true).get("total"));
    }
    @Test void rejectsFractionalPricesForZeroDecimalCurrency() {
        assertThrows(Problem.class,()->purchase("JPY","1","1.01").normalized(true));
    }
    @Test void permitsIncompleteDraftButPreventsSubmission() {
        var draft=new Purchase("","","USD","","",List.of());
        assertEquals("0.00",draft.normalized(false).get("total"));
        assertThrows(Problem.class,()->draft.normalized(true));
    }
}
