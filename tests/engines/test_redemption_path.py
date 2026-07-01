from decimal import Decimal

from lmt_calibration.domain import (
    AssetGroup,
    AssetPosition,
    ClientClass,
    FundSnapshot,
    InstrumentSubtype,
    InvestorClassProfile,
    LiquidationStrategyConfig,
    LiquidationStrategyType,
    LiquidityExecutionAssumption,
    LiquidityStress,
    LmtParameters,
    MarketStress,
    PathLmtOutcome,
    RedemptionPathAssumptions,
    RedemptionPathResult,
)
from lmt_calibration.engines.redemption_path import run_redemption_path


def test_redemption_path_returns_twelve_months_and_carries_nav_forward() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(
            _cash("200"),
            _equity("euro_equity", "800"),
        ),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0.02", "0"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="twelve_month_path",
            start_date="2026-01-01",
            random_seed=11,
        ),
    )

    assert len(result.monthly_results) == 12
    assert result.monthly_results[1].opening_nav == result.monthly_results[0].closing_nav


def test_redemption_path_is_deterministic_for_fixed_seed() -> None:
    first = _deterministic_path_result()
    second = _deterministic_path_result()

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_market_stress_is_applied_once_in_selected_month() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(
            _cash("100"),
            _equity("euro_equity", "900"),
        ),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="market_once",
            start_date="2026-01-01",
            random_seed=1,
            stress_months=(2, 3),
            market_stress_month=2,
        ),
        market_stress=MarketStress(
            market_stress_id="severe_equity_stress",
            version="1.0",
            name="severe_equity_stress",
            description="Synthetic severe equity stress.",
            market_shock_rate=Decimal("-0.10"),
        ),
    )

    assert [month.market_stress_applied for month in result.monthly_results[:3]] == [
        False,
        True,
        False,
    ]
    month_2_equity = _position_value(result.monthly_results[1].positions, "euro_equity")
    month_3_equity = _position_value(result.monthly_results[2].positions, "euro_equity")
    assert month_2_equity == Decimal("810.00")
    assert month_3_equity == Decimal("810.00")


def test_empty_stress_months_does_not_error() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(
            _cash("100"),
            _equity("euro_equity", "900"),
        ),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0.02", "0.50"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="no_stress_months",
            start_date="2026-01-01",
            random_seed=42,
            stress_months=(),
        ),
    )

    assert len(result.monthly_results) == 12
    assert all(month.opening_nav > Decimal("0") for month in result.monthly_results)


def test_market_contagion_adjusts_only_next_month_liquidity_cost_rate() -> None:
    base_arguments = {
        "fund": _fund(),
        "positions": (_cash("100"), _equity("euro_equity", "900")),
        "investor_profiles": (_investor(ClientClass.RETAIL, "1", "0", "0.10"),),
        "liquidity_stress": _liquidity_stress_with_cost("0.01"),
        "liquidation_strategy": _strategy(),
        "lmt_parameters": _parameters(gate_threshold="1"),
        "market_stress": MarketStress(
            market_stress_id="market_contagion_stress",
            version="1.0",
            name="market_contagion_stress",
            description="Synthetic market stress for liquidity-cost spillover.",
            market_shock_rate=Decimal("-0.10"),
        ),
    }
    enabled = run_redemption_path(
        **base_arguments,
        assumptions=RedemptionPathAssumptions(
            scenario_id="market_contagion_comparison",
            start_date="2026-01-01",
            random_seed=1,
            stress_months=(1, 2, 3),
            market_stress_month=1,
            market_contagion_liquidity_cost_multiplier=Decimal("2"),
        ),
    )
    disabled = run_redemption_path(
        **base_arguments,
        assumptions=RedemptionPathAssumptions(
            scenario_id="market_contagion_comparison",
            start_date="2026-01-01",
            random_seed=1,
            stress_months=(1, 2, 3),
            market_stress_month=1,
        ),
    )

    assert [month.market_contagion_applied for month in enabled.monthly_results[:3]] == [
        False,
        True,
        False,
    ]
    assert enabled.monthly_results[0].liquidation_result.total_realised_execution_cost == Decimal(
        "0"
    )
    assert enabled.monthly_results[2].liquidation_result.total_realised_execution_cost == Decimal(
        "0"
    )
    second_month = enabled.monthly_results[1]
    assert second_month.market_contagion_liquidity_cost_multiplier == Decimal("2")
    assert second_month.adjusted_estimated_liquidity_cost_rate == (
        second_month.base_estimated_liquidity_cost_rate * Decimal("2")
    )
    assert second_month.investor_class_states == disabled.monthly_results[1].investor_class_states
    disabled_second_month = disabled.monthly_results[1]
    assert second_month.lmt_assessment.paid_redemption_amount == (
        disabled_second_month.lmt_assessment.paid_redemption_amount
    )
    assert second_month.liquidation_result.total_realised_execution_cost > Decimal("0")
    assert second_month.liquidation_result.total_haircut_cost == (
        disabled_second_month.liquidation_result.total_haircut_cost
    )
    assert sum(
        asset.gross_sale_amount for asset in second_month.liquidation_result.assets_liquidated
    ) > sum(
        asset.gross_sale_amount
        for asset in disabled_second_month.liquidation_result.assets_liquidated
    )
    assert second_month.closing_nav < disabled_second_month.closing_nav


def test_reverse_repo_maturity_becomes_cash_before_liquidation() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(
            _cash("0"),
            _reverse_repo("overnight_reverse_repo", "100", maturity_days=15),
            _equity("euro_equity", "900"),
        ),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="reverse_repo_cashflow",
            start_date="2026-01-01",
            random_seed=1,
        ),
    )

    first_month = result.monthly_results[0]
    assert first_month.contractual_cashflow_amount == Decimal("100")
    assert first_month.closing_cash == Decimal("100")
    assert _position_value(first_month.positions, "overnight_reverse_repo") == Decimal("0")


def test_monthly_liquidation_capacity_scales_daily_capacity_by_available_days() -> None:
    arguments = {
        "fund": _fund(),
        "positions": (
            _equity("euro_equity", "1000").model_copy(
                update={"base_liquidity_capacity_rate": Decimal("0.025")}
            ),
        ),
        "investor_profiles": (_investor(ClientClass.RETAIL, "1", "0", "0.50"),),
        "liquidity_stress": _liquidity_stress(),
        "liquidation_strategy": _strategy(),
        "lmt_parameters": _parameters(gate_threshold="1"),
    }
    daily_capacity_path = run_redemption_path(
        **arguments,
        assumptions=RedemptionPathAssumptions(
            scenario_id="daily_capacity_path",
            start_date="2026-01-01",
            random_seed=1,
            stress_months=(1,),
            liquidation_days_per_month=1,
        ),
    )
    monthly_capacity_path = run_redemption_path(
        **arguments,
        assumptions=RedemptionPathAssumptions(
            scenario_id="monthly_capacity_path",
            start_date="2026-01-01",
            random_seed=1,
            stress_months=(1,),
            liquidation_days_per_month=20,
        ),
    )

    daily_result = daily_capacity_path.monthly_results[0].liquidation_result
    monthly_result = monthly_capacity_path.monthly_results[0].liquidation_result

    assert daily_result.total_net_cash_raised == Decimal("25.0000")
    assert daily_result.shortfall == Decimal("475.0000")
    assert monthly_result.total_net_cash_raised == Decimal("500.00")
    assert monthly_result.shortfall == Decimal("0.00")


def test_monthly_liquidation_capacity_is_capped_at_position_value() -> None:
    result = (
        run_redemption_path(
            fund=_fund(),
            positions=(
                _equity("euro_equity", "1000").model_copy(
                    update={
                        "base_haircut_rate": Decimal("0.50"),
                        "base_liquidity_capacity_rate": Decimal("0.10"),
                    }
                ),
            ),
            investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "1"),),
            liquidity_stress=_liquidity_stress(),
            liquidation_strategy=_strategy(),
            lmt_parameters=_parameters(gate_threshold="1"),
            assumptions=RedemptionPathAssumptions(
                scenario_id="monthly_capacity_cap",
                start_date="2026-01-01",
                random_seed=1,
                stress_months=(1,),
                liquidation_days_per_month=20,
            ),
        )
        .monthly_results[0]
        .liquidation_result
    )

    assert result.assets_liquidated[0].gross_sale_amount == Decimal("1000")
    assert result.total_net_cash_raised == Decimal("500.00")
    assert result.shortfall == Decimal("500.00")


def test_gate_paid_redemptions_are_allocated_pro_rata_and_backlog_carries_forward() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(
            _cash("300"),
            _equity("euro_equity", "700"),
        ),
        investor_profiles=(
            _investor(ClientClass.RETAIL, "0.50", "0", "0.50"),
            _investor(ClientClass.INSTITUTIONAL, "0.50", "0", "0.50"),
        ),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="0.10"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="gate_backlog",
            start_date="2026-01-01",
            random_seed=1,
            stress_months=(1,),
            gate_months=(1,),
        ),
    )

    first_month = result.monthly_results[0]
    states = {state.client_class: state for state in first_month.investor_class_states}

    assert first_month.lmt_assessment.gate_signal is True
    assert first_month.lmt_assessment.gate_applied is True
    assert first_month.lmt_assessment.paid_redemption_amount == Decimal("100.0")
    assert states[ClientClass.RETAIL].paid_redemption_amount == Decimal("50.00")
    assert states[ClientClass.INSTITUTIONAL].paid_redemption_amount == Decimal("50.00")
    assert states[ClientClass.RETAIL].deferred_redemption_amount == Decimal("200.00")
    assert states[ClientClass.INSTITUTIONAL].deferred_redemption_amount == Decimal("200.00")
    assert sum((entry.remaining_amount for entry in first_month.backlog), Decimal("0")) == Decimal(
        "400.00"
    )
    assert result.monthly_results[1].investor_class_states[0].opening_backlog_amount > Decimal("0")


def test_threshold_breach_and_liquidity_shortfall_do_not_create_lmt_backlog() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash("0"), _equity("euro_equity", "1000")),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0.50"),),
        liquidity_stress=LiquidityStress(
            liquidity_stress_id="constrained_signal_only_liquidity",
            version="1.0",
            name="constrained_signal_only_liquidity",
            description="Synthetic constrained liquidity for signal-only testing.",
            stress_horizon_days=5,
            execution_assumptions_by_asset_group={
                AssetGroup.CASH: _execution_assumption(),
                AssetGroup.LISTED_EQUITY: LiquidityExecutionAssumption(
                    bid_ask_spread_rate=Decimal("0"),
                    transaction_cost_rate=Decimal("0"),
                    market_impact_rate=Decimal("0"),
                    participation_rate=Decimal("0.20"),
                    liquidity_haircut_rate=Decimal("0"),
                ),
            },
        ),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="0.10"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="signal_only_with_liquidity_shortfall",
            start_date="2026-01-01",
            random_seed=1,
            stress_months=(1,),
            liquidation_days_per_month=1,
        ),
    )

    first_month = result.monthly_results[0]

    assert first_month.lmt_assessment.gate_signal is True
    assert first_month.lmt_assessment.gate_applied is False
    assert first_month.lmt_assessment.suspension_applied is False
    assert first_month.liquidation_result.shortfall == Decimal("300.00")
    assert first_month.lmt_assessment.deferred_redemption_amount == Decimal("0.00")
    assert all(
        state.deferred_redemption_amount == Decimal("0.00")
        for state in first_month.investor_class_states
    )
    assert first_month.backlog == ()


def test_full_payment_path_does_not_create_decimal_backlog_dust() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash("1000"),),
        investor_profiles=(
            _investor(ClientClass.RETAIL, "0.3333333333333333333333333333", "0", "0.10"),
            _investor(
                ClientClass.INSTITUTIONAL,
                "0.6666666666666666666666666667",
                "0",
                "0.10",
            ),
        ),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="no_backlog_decimal_dust",
            start_date="2026-01-01",
            random_seed=1,
            stress_months=(1,),
        ),
    )

    assert all(month.backlog == () for month in result.monthly_results)
    assert all(
        state.deferred_redemption_amount == Decimal("0")
        for month in result.monthly_results
        for state in month.investor_class_states
    )


def test_swing_outcome_applies_next_month_behavioural_feedback_multiplier() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash("1000"),),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0.10"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(swing_threshold="0.05", gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="swing_feedback",
            start_date="2026-01-01",
            random_seed=3,
            stress_months=(1, 2),
            swing_pricing_months=(1,),
            behavioural_feedback_multipliers_by_outcome={
                PathLmtOutcome.SWING_PRICING: {ClientClass.RETAIL: Decimal("2")}
            },
        ),
    )

    assert (
        result.monthly_results[0].behavioural_feedback_adjustment.source_outcome
        is PathLmtOutcome.NONE
    )
    assert result.monthly_results[0].investor_class_states[0].redemption_rate == Decimal("0.10")
    assert result.monthly_results[0].lmt_assessment.priority_outcome is PathLmtOutcome.SWING_PRICING
    assert (
        result.monthly_results[1].behavioural_feedback_adjustment.source_outcome
        is PathLmtOutcome.SWING_PRICING
    )
    assert result.monthly_results[1].investor_class_states[0].redemption_rate == Decimal("0.20")


def test_gate_outcome_applies_next_month_behavioural_feedback_multiplier() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash("1000"),),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0.50"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(swing_threshold="1", gate_threshold="0.10"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="gate_feedback",
            start_date="2026-01-01",
            random_seed=3,
            stress_months=(1, 2),
            gate_months=(1,),
            behavioural_feedback_multipliers_by_outcome={
                PathLmtOutcome.REDEMPTION_GATE: {ClientClass.RETAIL: Decimal("1.50")}
            },
        ),
    )

    assert (
        result.monthly_results[0].lmt_assessment.priority_outcome is PathLmtOutcome.REDEMPTION_GATE
    )
    assert (
        result.monthly_results[1].behavioural_feedback_adjustment.source_outcome
        is PathLmtOutcome.REDEMPTION_GATE
    )
    assert result.monthly_results[1].investor_class_states[0].redemption_rate == Decimal("0.750")


def test_liquidity_buffer_breach_is_a_signal_without_behavioural_feedback() -> None:
    unconfigured = _buffer_breach_path({})
    configured = _buffer_breach_path(
        {PathLmtOutcome.LIQUIDITY_BUFFER_BREACH: {ClientClass.RETAIL: Decimal("1.50")}}
    )

    assert unconfigured.monthly_results[0].lmt_assessment.buffer_breached is True
    assert unconfigured.monthly_results[0].lmt_assessment.priority_outcome is PathLmtOutcome.NONE
    assert unconfigured.monthly_results[1].investor_class_states[0].redemption_rate == Decimal(
        "0.10"
    )
    assert configured.monthly_results[1].investor_class_states[0].redemption_rate == Decimal("0.10")


def test_behavioural_feedback_multiplier_one_is_neutral_after_outcome() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash("1000"),),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0.10"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(swing_threshold="0.05", gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="neutral_behavioural_feedback",
            start_date="2026-01-01",
            random_seed=3,
            stress_months=(1, 2),
            swing_pricing_months=(1,),
            behavioural_feedback_multipliers_by_outcome={
                PathLmtOutcome.SWING_PRICING: {ClientClass.RETAIL: Decimal("1")}
            },
        ),
    )

    assert (
        result.monthly_results[1].behavioural_feedback_adjustment.source_outcome
        is PathLmtOutcome.SWING_PRICING
    )
    assert result.monthly_results[1].investor_class_states[0].redemption_rate == Decimal("0.10")


def test_no_outcome_gives_neutral_next_month_multipliers() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash("1000"),),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="neutral_feedback",
            start_date="2026-01-01",
            random_seed=3,
        ),
    )

    assert result.monthly_results[0].lmt_assessment.priority_outcome is PathLmtOutcome.NONE
    assert (
        result.monthly_results[1].behavioural_feedback_adjustment.source_outcome
        is PathLmtOutcome.NONE
    )
    assert result.monthly_results[
        1
    ].behavioural_feedback_adjustment.behavioural_feedback_multipliers[
        ClientClass.RETAIL
    ] == Decimal("1")


def test_multiple_outcomes_use_priority_order() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash("1000"),),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0.50"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(
            swing_threshold="0.05",
            gate_threshold="0.10",
            minimum_buffer="0.50",
        ),
        assumptions=RedemptionPathAssumptions(
            scenario_id="priority_feedback",
            start_date="2026-01-01",
            random_seed=3,
            stress_months=(1, 2),
            swing_pricing_months=(1,),
            gate_months=(1,),
            behavioural_feedback_multipliers_by_outcome={
                PathLmtOutcome.SWING_PRICING: {ClientClass.RETAIL: Decimal("2")},
                PathLmtOutcome.REDEMPTION_GATE: {ClientClass.RETAIL: Decimal("1.50")},
            },
        ),
    )

    first_assessment = result.monthly_results[0].lmt_assessment
    assert first_assessment.swing_applied is True
    assert first_assessment.gate_applied is True
    assert first_assessment.priority_outcome is PathLmtOutcome.REDEMPTION_GATE
    assert result.monthly_results[1].investor_class_states[0].redemption_rate == Decimal("0.750")


def test_behavioural_feedback_expires_without_another_activation() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash("1000"),),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0.20"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(swing_threshold="0.15", gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="one_month_feedback",
            start_date="2026-01-01",
            random_seed=3,
            stress_months=(1,),
            swing_pricing_months=(1,),
            behavioural_feedback_multipliers_by_outcome={
                PathLmtOutcome.SWING_PRICING: {ClientClass.RETAIL: Decimal("1.50")}
            },
        ),
    )

    assert result.monthly_results[0].lmt_assessment.priority_outcome is PathLmtOutcome.SWING_PRICING
    assert (
        result.monthly_results[1].behavioural_feedback_adjustment.source_outcome
        is PathLmtOutcome.SWING_PRICING
    )
    assert result.monthly_results[1].investor_class_states[0].redemption_rate == Decimal("0")
    assert result.monthly_results[1].lmt_assessment.priority_outcome is PathLmtOutcome.NONE
    assert (
        result.monthly_results[2].behavioural_feedback_adjustment.source_outcome
        is PathLmtOutcome.NONE
    )
    assert result.monthly_results[2].investor_class_states[0].redemption_rate == Decimal("0")


def test_repeated_lmt_activations_trigger_repeated_following_month_feedback() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash("1000"),),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0.10"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(swing_threshold="0.05", gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="repeated_behavioural_feedback",
            start_date="2026-01-01",
            random_seed=3,
            stress_months=(1, 2, 3),
            swing_pricing_months=(1, 2, 3),
            behavioural_feedback_multipliers_by_outcome={
                PathLmtOutcome.SWING_PRICING: {ClientClass.RETAIL: Decimal("1.50")}
            },
        ),
    )

    assert [month.lmt_assessment.swing_applied for month in result.monthly_results[:3]] == [
        True,
        True,
        True,
    ]
    assert [
        month.investor_class_states[0].redemption_rate for month in result.monthly_results[:3]
    ] == [Decimal("0.10"), Decimal("0.150"), Decimal("0.150")]


def test_backlog_is_not_multiplied_again_by_behavioural_feedback() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash("1000"),),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0.50"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(swing_threshold="1", gate_threshold="0.10"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="backlog_not_multiplied",
            start_date="2026-01-01",
            random_seed=3,
            stress_months=(1, 2),
            gate_months=(1,),
            behavioural_feedback_multipliers_by_outcome={
                PathLmtOutcome.REDEMPTION_GATE: {ClientClass.RETAIL: Decimal("2")}
            },
        ),
    )

    first_backlog = result.monthly_results[0].backlog[0].remaining_amount
    second_state = result.monthly_results[1].investor_class_states[0]

    assert first_backlog == Decimal("400.0")
    assert second_state.opening_backlog_amount == first_backlog
    assert second_state.new_redemption_amount == Decimal("500.0")


def test_backlog_and_new_demand_do_not_exceed_remaining_investor_capital() -> None:
    initial_nav = Decimal("1000")
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash("1000"),),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0.50"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(swing_threshold="1", gate_threshold="0.10"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="bounded_redemption_demand",
            start_date="2026-01-01",
            random_seed=3,
            stress_months=tuple(range(1, 13)),
            gate_months=tuple(range(1, 13)),
            behavioural_feedback_multipliers_by_outcome={
                PathLmtOutcome.REDEMPTION_GATE: {ClientClass.RETAIL: Decimal("3")}
            },
        ),
    )

    for month in result.monthly_results:
        effective_demand = sum(
            (state.effective_redemption_amount for state in month.investor_class_states),
            Decimal("0"),
        )
        assert effective_demand <= initial_nav

    assert result.monthly_results[1].investor_class_states[0].new_redemption_amount == Decimal(
        "500.0"
    )


def test_liquidation_still_uses_paid_redemption_only() -> None:
    result = run_redemption_path(
        fund=_fund(),
        positions=(_cash("300"), _equity("euro_equity", "700")),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0.50"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(swing_threshold="1", gate_threshold="0.10"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="paid_only_liquidation",
            start_date="2026-01-01",
            random_seed=3,
            stress_months=(1,),
            gate_months=(1,),
        ),
    )

    first_month = result.monthly_results[0]
    assert first_month.lmt_assessment.paid_redemption_amount == Decimal("100.0")
    assert first_month.liquidation_result.total_redemption_amount == Decimal("100.0")
    assert first_month.lmt_assessment.deferred_redemption_amount == Decimal("400.0")


def _fund() -> FundSnapshot:
    return FundSnapshot(
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-01-01",
        fund_name="Lux Dynamic Allocation Fund",
        base_currency="EUR",
        nav=Decimal("1000"),
        dealing_frequency="daily",
        redemption_notice_days=1,
        redemption_settlement_days=3,
    )


def _deterministic_path_result():
    return run_redemption_path(
        fund=_fund(),
        positions=(
            _cash("200"),
            _equity("euro_equity", "800"),
        ),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0.02", "0"),),
        liquidity_stress=_liquidity_stress(),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(gate_threshold="1"),
        assumptions=RedemptionPathAssumptions(
            scenario_id="deterministic_path",
            start_date="2026-01-01",
            random_seed=42,
        ),
    )


def _cash(market_value: str) -> AssetPosition:
    return AssetPosition(
        position_id="eur_operating_cash",
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-01-01",
        asset_group=AssetGroup.CASH,
        instrument_type="cash",
        instrument_subtype=InstrumentSubtype.CASH,
        instrument_name="EUR Operating Cash",
        currency="EUR",
        market_value=Decimal(market_value),
        base_haircut_rate=Decimal("0"),
        base_liquidity_capacity_rate=Decimal("1"),
        settlement_days=0,
    )


def _equity(position_id: str, market_value: str) -> AssetPosition:
    return AssetPosition(
        position_id=position_id,
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-01-01",
        asset_group=AssetGroup.LISTED_EQUITY,
        instrument_type="listed_equity",
        instrument_subtype=InstrumentSubtype.LISTED_EQUITY,
        instrument_name="Synthetic European Equity Holding",
        ticker="SYN GY",
        currency="EUR",
        market_value=Decimal(market_value),
        risk_factor_id="europe_equity",
        beta=Decimal("1"),
        base_haircut_rate=Decimal("0"),
        base_liquidity_capacity_rate=Decimal("1"),
        settlement_days=2,
    )


def _reverse_repo(position_id: str, market_value: str, maturity_days: int) -> AssetPosition:
    return AssetPosition(
        position_id=position_id,
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-01-01",
        asset_group=AssetGroup.REVERSE_REPO,
        instrument_type="reverse_repo",
        instrument_subtype=InstrumentSubtype.REVERSE_REPO,
        instrument_name="EUR Reverse Repo Synthetic",
        currency="EUR",
        market_value=Decimal(market_value),
        base_haircut_rate=Decimal("0"),
        base_liquidity_capacity_rate=Decimal("1"),
        settlement_days=1,
        maturity_days=maturity_days,
    )


def _investor(
    client_class: ClientClass,
    nav_share: str,
    base_rate: str,
    stress_rate: str,
) -> InvestorClassProfile:
    return InvestorClassProfile(
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-01-01",
        client_class=client_class,
        nav_share_rate=Decimal(nav_share),
        base_redemption_rate=Decimal(base_rate),
        stress_redemption_rate=Decimal(stress_rate),
        concentration_factor=Decimal("0.50"),
        notice_days=1,
        settlement_days=3,
    )


def _liquidity_stress() -> LiquidityStress:
    assumptions = {
        AssetGroup.CASH: _execution_assumption(),
        AssetGroup.LISTED_EQUITY: _execution_assumption(),
        AssetGroup.REVERSE_REPO: _execution_assumption(),
    }
    return LiquidityStress(
        liquidity_stress_id="normal_liquidity",
        version="1.0",
        name="normal_liquidity",
        description="Synthetic normal liquidity.",
        stress_horizon_days=5,
        execution_assumptions_by_asset_group=assumptions,
    )


def _liquidity_stress_with_cost(cost_rate: str) -> LiquidityStress:
    cost_assumption = LiquidityExecutionAssumption(
        bid_ask_spread_rate=Decimal(cost_rate),
        transaction_cost_rate=Decimal("0"),
        market_impact_rate=Decimal("0"),
        participation_rate=Decimal("1"),
        liquidity_haircut_rate=Decimal("0"),
    )
    return LiquidityStress(
        liquidity_stress_id="liquidity_cost_stress",
        version="1.0",
        name="liquidity_cost_stress",
        description="Synthetic liquidity stress with execution cost.",
        stress_horizon_days=5,
        execution_assumptions_by_asset_group={
            AssetGroup.CASH: cost_assumption,
            AssetGroup.LISTED_EQUITY: cost_assumption,
            AssetGroup.REVERSE_REPO: cost_assumption,
        },
    )


def _execution_assumption() -> LiquidityExecutionAssumption:
    return LiquidityExecutionAssumption(
        bid_ask_spread_rate=Decimal("0"),
        transaction_cost_rate=Decimal("0"),
        market_impact_rate=Decimal("0"),
        participation_rate=Decimal("1"),
        liquidity_haircut_rate=Decimal("0"),
    )


def _strategy() -> LiquidationStrategyConfig:
    return LiquidationStrategyConfig(
        liquidation_strategy_id="cash_then_liquid_assets",
        version="1.0",
        name="cash_then_liquid_assets",
        description="Synthetic most-liquid-first strategy.",
        strategy_type=LiquidationStrategyType.MOST_LIQUID_FIRST,
        preserve_minimum_buffer=True,
    )


def _parameters(
    gate_threshold: str,
    *,
    swing_threshold: str = "1",
    minimum_buffer: str = "0",
) -> LmtParameters:
    return LmtParameters(
        fund_id="lux_dynamic_allocation",
        as_of_date="2026-01-01",
        parameter_set_id="path_parameters",
        swing_threshold_rate=Decimal(swing_threshold),
        max_swing_factor_rate=Decimal("0.03"),
        gate_threshold_rate=Decimal(gate_threshold),
        minimum_buffer_rate=Decimal(minimum_buffer),
    )


def _position_value(positions: tuple, position_id: str) -> Decimal:
    return next(
        position.market_value for position in positions if position.position_id == position_id
    )


def _buffer_breach_path(
    behavioural_feedback_multipliers: dict[
        PathLmtOutcome,
        dict[ClientClass, Decimal],
    ],
) -> RedemptionPathResult:
    return run_redemption_path(
        fund=_fund(),
        positions=(_cash("0"), _equity("euro_equity", "1000")),
        investor_profiles=(_investor(ClientClass.RETAIL, "1", "0", "0.10"),),
        liquidity_stress=LiquidityStress(
            liquidity_stress_id="constrained_liquidity",
            version="1.0",
            name="constrained_liquidity",
            description="Synthetic constrained liquidity.",
            stress_horizon_days=5,
            execution_assumptions_by_asset_group={
                AssetGroup.CASH: _execution_assumption(),
                AssetGroup.LISTED_EQUITY: LiquidityExecutionAssumption(
                    bid_ask_spread_rate=Decimal("0"),
                    transaction_cost_rate=Decimal("0"),
                    market_impact_rate=Decimal("0"),
                    participation_rate=Decimal("0.20"),
                    liquidity_haircut_rate=Decimal("0"),
                ),
            },
        ),
        liquidation_strategy=_strategy(),
        lmt_parameters=_parameters(
            swing_threshold="1",
            gate_threshold="1",
            minimum_buffer="0.50",
        ),
        assumptions=RedemptionPathAssumptions(
            scenario_id="buffer_feedback",
            start_date="2026-01-01",
            random_seed=3,
            stress_months=(1, 2),
            liquidation_days_per_month=1,
            behavioural_feedback_multipliers_by_outcome=behavioural_feedback_multipliers,
        ),
    )
