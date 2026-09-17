package dev.caseflow.cases;

import dev.caseflow.common.Problem;
import java.math.BigDecimal;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
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
    @ParameterizedTest
    @ValueSource(strings={"ZZZ","XXX"})
    void rejectsUnknownCurrencyAndIsoCodesWithoutUsableMinorUnits(String currency) {
        assertEquals(400,assertThrows(Problem.class,()->purchase(currency,"1","1").normalized(false)).status);
    }
    @ParameterizedTest
    @ValueSource(strings={"description","costCenter","justification","lineItems"})
    void everyRequiredSubmissionFieldIsCheckedAfterAValidVendor(String missing) {
        var draft=new Purchase("Vendor",missing.equals("description")?"  ":"Equipment","USD",
                missing.equals("costCenter")?"\t":"OPS",missing.equals("justification")?"\n":"Required for work",
                missing.equals("lineItems")?List.of():List.of(new Purchase.Item("Item",BigDecimal.ONE,BigDecimal.ONE)));
        assertDoesNotThrow(()->draft.normalized(false));
        assertEquals(400,assertThrows(Problem.class,()->draft.normalized(true)).status);
    }
    @Test void aBlankLineDescriptionCanBeSavedAsADraftButCannotBeSubmitted() {
        var draft=new Purchase("Vendor","Equipment","USD","OPS","Required for work",
                List.of(new Purchase.Item("  ",BigDecimal.ONE,BigDecimal.ONE)));
        assertEquals("1.00",draft.normalized(false).get("total"));
        assertEquals(400,assertThrows(Problem.class,()->draft.normalized(true)).status);
    }
    @Test void acceptsTrailingZerosAndThreeDecimalCurrencyWithoutBinaryRounding() {
        assertEquals("1.23",purchase("USD","1","1.2300").normalized(true).get("total"));
        assertEquals("1.235",purchase("BHD","0.5","2.469").normalized(true).get("total"));
    }
    @Test void rejectsATotalThatOverflowsEvenWhenEachQuantityAndPriceIsWithinItsFieldLimit() {
        assertEquals(400,assertThrows(Problem.class,()->purchase("USD","99999999","999999999999.00").normalized(true)).status);
    }
}
