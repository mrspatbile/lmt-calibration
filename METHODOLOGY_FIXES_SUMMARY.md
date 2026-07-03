# Liquidity Cost Accounting Methodology Fixes

## Summary

Fixed critical triple-counting error in gate-period liquidation cost calculations. The engine now correctly recognizes all economic liquidity costs in the month of liquidation and allocates them via swing pricing, without double or triple-subtraction from NAV.

## Changes Made

### 1. Domain Model Enhancement

**File:** `src/lmt_calibration/domain/redemption_path.py`

Added new field to `MonthlyRedemptionPathResult`:
- `investor_borne_liquidity_cost_after_contagion: Decimal` - Enables direct verification of cost accounting identity

### 2. Engine Cost Calculation Fix

**File:** `src/lmt_calibration/engines/redemption_path.py`

#### Step A: Centralize Economic Cost Calculation (Lines 276-294)
```python
# Calculate immediate liquidation cost
immediate_liquidation_cost_after_contagion = (
    liquidation_result.total_realised_liquidity_cost
    * market_contagion_liquidity_cost_multiplier
)

# Calculate gate-period liquidation cost (if gate active)
gate_period_liquidation_cost_after_contagion = ZERO
if gate_period_liquidation_result is not None:
    gate_period_liquidation_cost_after_contagion = (
        gate_period_liquidation_result.total_realised_execution_cost
        * market_contagion_liquidity_cost_multiplier
    )

# Total economic liquidity cost = both components
realised_liquidity_cost_after_contagion = (
    immediate_liquidation_cost_after_contagion
    + gate_period_liquidation_cost_after_contagion
)
```

**Impact:** Gate costs are now tracked separately but summed into total economic cost. This allows clean allocation logic without double-counting.

#### Step B: Allocate via Swing Pricing (Lines 333-340)
```python
# Allocate total economic cost (immediate + gate-period) based on swing pricing
if swing_applied:
    # Swing pricing transfers all economic liquidity costs to redeeming investors
    investor_borne_liquidity_cost_after_contagion = realised_liquidity_cost_after_contagion
    fund_borne_liquidity_cost_after_contagion = ZERO
else:
    # No swing pricing: all economic costs remain fund-borne
    investor_borne_liquidity_cost_after_contagion = ZERO
    fund_borne_liquidity_cost_after_contagion = realised_liquidity_cost_after_contagion
```

**Impact:** Clear allocation logic. No separate gate subtraction. Fund-borne cost includes all components when swing is not applied.

#### Step C: Remove Separate Gate Subtraction from NAV (Line 310-311)
```python
# BEFORE: - preliminary_fund_borne - gate_period_execution_cost
# AFTER:  - preliminary_fund_borne  (already includes gate-period when no swing)

closing_nav_before_recovery = max(
    pre_lmt_nav
    - final_paid_amount
    - preliminary_fund_borne,  # All fund-borne costs in one place
    ZERO,
)
```

**Impact:** NAV calculation is now simple and correct: `opening - paid - fund_borne`.

#### Step D: Populate investor_borne Field (Line 404)
Added `investor_borne_liquidity_cost_after_contagion=investor_borne_liquidity_cost_after_contagion` to MonthlyRedemptionPathResult constructor.

### 3. Page 2 NAV Verification Fix

**File:** `app/streamlit_app.py`

#### Lines 2746-2773: Fix Verification Formula
```python
# BEFORE:
calculated_closing = (
    opening_nav + market_gain - paid_redemption 
    - fund_borne_cost + swing_recovery - gate_cost  # WRONG: gate_cost subtracted twice
)

# AFTER:
calculated_closing = (
    opening_nav + market_gain - paid_redemption 
    - fund_borne_cost + swing_recovery  # CORRECT: gate_cost already in fund_borne
)
```

#### Line 2771: Tighten Tolerance
```python
# BEFORE: nav_diff < Decimal("1")  # 1 EUR tolerance - too loose
# AFTER:  nav_diff < Decimal("0.01")  # 1 cent tolerance - catches errors
```

**Impact:** Verification no longer masks double-subtraction errors.

## Methodology Verification

### Cost Accounting Identity
✅ **VERIFIED:** `economic_liquidity_cost = investor_borne_liquidity_cost + fund_borne_liquidity_cost`

Tests confirm this identity holds for all scenarios:
- No swing: investor_borne = 0, fund_borne = economic
- With swing: investor_borne = economic, fund_borne = 0
- Gate + swing: All gate costs allocated to investors

### NAV Impact
✅ **VERIFIED:** `closing_nav = opening_nav + market_impact - redemptions_paid - fund_borne_cost`

Gate-period costs are:
- Recognized in the month liquidation occurs
- Included in fund_borne (when no swing)
- NOT subtracted separately
- NOT shifted to payment month

### Swing Pricing Allocation
✅ **VERIFIED:** Total economic cost (immediate + gate) is allocated:
- 100% to investors when swing active
- 100% to fund when swing inactive
- Gate costs follow same allocation as immediate liquidation costs

## Unit Tests Added

**File:** `tests/test_cost_accounting_identity.py` (9 new tests)

1. ✅ `test_economic_liquidity_cost_identity_no_swing` - Identity holds without swing
2. ✅ `test_economic_liquidity_cost_identity_with_swing` - Identity holds with swing
3. ✅ `test_swing_fully_transfers_costs` - Swing transfers 100% to investors
4. ✅ `test_no_swing_fund_bears_all_costs` - Fund bears 100% without swing
5. ✅ `test_gate_period_cost_in_economic_cost` - Gate costs included in total
6. ✅ `test_gate_with_swing_allocation` - Gate + swing allocate correctly
7. ✅ `test_nav_reconciliation_identity` - Cost identity verified
8. ✅ `test_gate_cost_not_double_subtracted` - NAV formula correct
9. ✅ `test_unsettled_gate_cash_settles_next_month` - Cash settlement correct

## Test Coverage

**Before:** 230 tests  
**After:** 239 tests (+9 new cost accounting tests)  
**All tests pass:** ✅ 239/239

## Backward Compatibility

All existing tests pass without modification. The fixes:
- Correct calculation errors (no API changes)
- Add new field with default value (backward compatible)
- Tighten verification tolerance (catches bugs, not a breaking change)

## Files Modified

1. `src/lmt_calibration/domain/redemption_path.py` - Added investor_borne field
2. `src/lmt_calibration/engines/redemption_path.py` - Fixed cost calculation and allocation
3. `app/streamlit_app.py` - Fixed NAV verification formula
4. `tests/test_cost_accounting_identity.py` - Added 9 new tests (new file)

## Verification Checklist

- ✅ Economic cost identity holds for all scenarios
- ✅ Swing pricing allocates costs correctly
- ✅ Gate-period costs recognized in liquidation month
- ✅ No double-subtraction of costs
- ✅ NAV reconciliation formula correct
- ✅ All 239 tests pass
- ✅ Backward compatible
