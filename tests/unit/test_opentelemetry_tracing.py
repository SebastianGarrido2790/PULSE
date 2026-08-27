"""Unit tests for PULSE OpenTelemetry distributed tracing and child span nesting.

Verifies that solver, model, graph node, and post-match report child spans
are emitted with correct metadata attributes and hierarchical context propagation.

Authority: Phase 7 Decision D-10, Workflow Stage 2.
"""

from collections.abc import Generator

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.analytics.match_report import generate_match_report_async
from src.config.loader import load_params
from src.core.game_theory import PayoffMatrix, compute_exploit
from src.core.leverage_uncertainty import propagate_leverage_uncertainty
from src.core.markov_solver import MatchState, compute_leverage
from src.graph.state import PointContext, PulseGraphState
from src.graph.state_monitor import make_state_monitor_node
from src.models.point_win_classifier import (
    FallbackTier,
    StratumEntry,
    StratumTable,
    resolve_point_win_probability,
)
from src.models.pressure_deviation import (
    PressureBucketPrior,
    PressureDeviationResult,
    PressureModelArtifact,
    get_pressure_deviation,
)
from src.schemas.point_record import (
    PointOutcome,
    PointRecord,
    ServeDirection,
    Surface,
    ValidPointScore,
)

# Configure singleton in-memory exporter on module load
_GLOBAL_EXPORTER = InMemorySpanExporter()
_PROVIDER = TracerProvider()
_PROVIDER.add_span_processor(SimpleSpanProcessor(_GLOBAL_EXPORTER))
trace.set_tracer_provider(_PROVIDER)


@pytest.fixture(autouse=True)
def memory_exporter() -> Generator[InMemorySpanExporter, None, None]:
    """Provides a clean in-memory span exporter for each test."""
    _GLOBAL_EXPORTER.clear()
    yield _GLOBAL_EXPORTER
    _GLOBAL_EXPORTER.clear()


@pytest.fixture
def sample_stratum_table() -> StratumTable:
    """Sample StratumTable for testing."""
    return StratumTable(
        tier0_exact={"Alex De Minaur|HARD|1": StratumEntry(wins=65, sample_size=100, p_hat=0.65)},
        tier1_player={"Alex De Minaur|1": StratumEntry(wins=65, sample_size=100, p_hat=0.65)},
        tier2_surface={"HARD|1": StratumEntry(wins=600, sample_size=1000, p_hat=0.60)},
        global_default_p=0.62,
    )


@pytest.fixture
def sample_pressure_artifact() -> PressureModelArtifact:
    """Sample PressureModelArtifact for testing."""
    artifact = PressureModelArtifact(
        priors={
            2: PressureBucketPrior(
                leverage_bucket=2,
                alpha_0=10.0,
                beta_0=10.0,
                is_prior_estimated=True,
                player_count=50,
            )
        },
        results={},
    )
    artifact.results["Alex De Minaur|2"] = PressureDeviationResult(
        server_id="Alex De Minaur",
        leverage_bucket=2,
        k_pressure=12,
        n_pressure=20,
        baseline_p=0.65,
        shrunk_rate=0.61,
        pressure_deviation=-0.04,
        deviation_low_90=-0.08,
        deviation_high_90=-0.01,
        alpha_prior=10.0,
        beta_prior=10.0,
        is_prior_estimated=True,
        is_sufficient_sample=True,
    )
    return artifact


@pytest.fixture
def sample_payoff_matrix() -> PayoffMatrix:
    """Sample PayoffMatrix with sufficient sample size."""
    return PayoffMatrix(
        matrix=[[0.70, 0.45], [0.40, 0.65]],
        row_labels=["Wide", "T"],
        col_labels=["Cover Wide", "Cover T"],
        observation_counts=[[30, 20], [20, 30]],
        n_opp_total=100,
        server_id="Alex De Minaur",
        returner_id="Alexander Zverev",
        surface="HARD",
        serve_number=1,
    )


def test_markov_solver_child_span(memory_exporter: InMemorySpanExporter) -> None:
    """Verify compute_leverage emits span with expected attributes."""
    state = MatchState(
        point_score_server=2,
        point_score_returner=2,
        game_score_server=4,
        game_score_returner=4,
        set_score_server=1,
        set_score_returner=1,
        match_format="bo3",
    )
    res = compute_leverage(state, p_serve=0.65)
    assert res.leverage > 0.0

    spans = memory_exporter.get_finished_spans()
    solver_spans = [s for s in spans if s.name == "markov_solver.compute_leverage"]
    assert len(solver_spans) == 1
    span = solver_spans[0]
    assert span.attributes is not None
    assert span.attributes["pulse.p_serve"] == 0.65
    assert span.attributes["pulse.match_format"] == "bo3"
    assert "pulse.score_state" in span.attributes
    assert span.attributes["pulse.leverage"] == res.leverage


def test_leverage_uncertainty_child_span(memory_exporter: InMemorySpanExporter) -> None:
    """Verify propagate_leverage_uncertainty emits span and attributes."""
    state = MatchState(
        point_score_server=3,
        point_score_returner=3,
        game_score_server=5,
        game_score_returner=5,
        set_score_server=0,
        set_score_returner=0,
        match_format="bo3",
    )
    res = propagate_leverage_uncertainty(state, wins=65, sample_size=100)
    assert res.band_width >= 0.0

    spans = memory_exporter.get_finished_spans()
    unc_spans = [s for s in spans if s.name == "leverage_uncertainty.propagate"]
    assert len(unc_spans) == 1
    span = unc_spans[0]
    assert span.attributes is not None
    assert span.attributes["pulse.sample_size"] == 100
    assert span.attributes["pulse.wins"] == 65
    assert span.attributes["pulse.is_sufficient_sample"] is True
    assert span.attributes["pulse.band_width"] == res.band_width


def test_point_win_classifier_child_span(
    memory_exporter: InMemorySpanExporter, sample_stratum_table: StratumTable
) -> None:
    """Verify resolve_point_win_probability emits span with metadata."""
    res = resolve_point_win_probability(
        sample_stratum_table, server_id="Alex De Minaur", surface="HARD", serve_number=1
    )
    assert res.fallback_tier == FallbackTier.EXACT_STRATUM

    spans = memory_exporter.get_finished_spans()
    p_spans = [s for s in spans if s.name == "point_win_classifier.resolve_probability"]
    assert len(p_spans) == 1
    span = p_spans[0]
    assert span.attributes is not None
    assert span.attributes["pulse.server_id"] == "Alex De Minaur"
    assert span.attributes["pulse.surface"] == "HARD"
    assert span.attributes["pulse.serve_number"] == 1
    assert span.attributes["pulse.fallback_tier"] == 0


def test_pressure_deviation_child_span(
    memory_exporter: InMemorySpanExporter, sample_pressure_artifact: PressureModelArtifact
) -> None:
    """Verify get_pressure_deviation emits span and attributes."""
    res = get_pressure_deviation(sample_pressure_artifact, "Alex De Minaur", 2)
    assert res is not None

    spans = memory_exporter.get_finished_spans()
    dev_spans = [s for s in spans if s.name == "pressure_deviation.get_deviation"]
    assert len(dev_spans) == 1
    span = dev_spans[0]
    assert span.attributes is not None
    assert span.attributes["pulse.server_id"] == "Alex De Minaur"
    assert span.attributes["pulse.leverage_bucket"] == 2
    assert span.attributes["pulse.hit"] is True
    assert span.attributes["pulse.pressure_deviation"] == -0.04


def test_game_theory_child_span(
    memory_exporter: InMemorySpanExporter, sample_payoff_matrix: PayoffMatrix
) -> None:
    """Verify compute_exploit emits span and attributes."""
    cfg = load_params()
    res = compute_exploit(sample_payoff_matrix, cfg)
    assert res.sufficient_data is True

    spans = memory_exporter.get_finished_spans()
    gt_spans = [s for s in spans if s.name == "game_theory.compute_exploit"]
    assert len(gt_spans) == 1
    span = gt_spans[0]
    assert span.attributes is not None
    assert span.attributes["pulse.n_opp_total"] == 100
    assert span.attributes["pulse.sufficient_data"] is True
    assert span.attributes["pulse.best_response_action"] in ("Wide", "T")


@pytest.mark.asyncio
async def test_state_monitor_node_span_nesting(
    memory_exporter: InMemorySpanExporter, sample_stratum_table: StratumTable
) -> None:
    """Verify state_monitor_node creates parent span enclosing classifier & solver child spans."""
    node = make_state_monitor_node(sample_stratum_table)
    ctx = PointContext(
        match_id="m1",
        point_index=1,
        server_id="Alex De Minaur",
        returner_id="Alexander Zverev",
        surface="HARD",
        serve_number=1,
        set_score_server=0,
        set_score_returner=0,
        game_score_server=1,
        game_score_returner=1,
        point_score_server=1,
        point_score_returner=2,
        match_format="bo3",
    )
    state = PulseGraphState(point_context=ctx)
    await node(state)

    spans = memory_exporter.get_finished_spans()
    span_names = [s.name for s in spans]
    assert "state_monitor_node" in span_names
    assert "point_win_classifier.resolve_probability" in span_names
    assert "leverage_uncertainty.propagate" in span_names
    assert "markov_solver.compute_leverage" in span_names

    parent_span = next(s for s in spans if s.name == "state_monitor_node")
    assert parent_span.context is not None
    parent_span_id = parent_span.context.span_id
    child_spans = [
        s
        for s in spans
        if s.parent is not None and getattr(s.parent, "span_id", None) == parent_span_id
    ]

    # Classifier and uncertainty propagation spans should nest directly under parent node
    child_names = [s.name for s in child_spans]
    assert "point_win_classifier.resolve_probability" in child_names
    assert "leverage_uncertainty.propagate" in child_names


@pytest.mark.asyncio
async def test_post_match_report_async_span_nesting(
    memory_exporter: InMemorySpanExporter,
) -> None:
    """Verify generate_match_report_async creates parent span enclosing evaluation spans."""
    records = [
        PointRecord(
            match_id="test_span_match",
            point_id="pt_1",
            server="Alex De Minaur",
            returner="Alexander Zverev",
            server_is_p1=True,
            surface=Surface.HARD,
            serve_number=1,
            serve_direction=ServeDirection.WIDE,
            p1_score=ValidPointScore.S0,
            p2_score=ValidPointScore.S0,
            p1_games=0,
            p2_games=0,
            p1_sets=0,
            p2_sets=0,
            point_winner=PointOutcome.SERVER,
        )
    ]
    # Pass mock client to bypass external API call
    report = await generate_match_report_async(
        records, llm_client=lambda *args, **kwargs: "Mock executive debrief."
    )
    assert report.summary.match_id == "test_span_match"

    spans = memory_exporter.get_finished_spans()
    span_names = [s.name for s in spans]
    assert "match_report.generate_async" in span_names
    assert "match_report.evaluate_all_points" in span_names

    gen_span = next(s for s in spans if s.name == "match_report.generate_async")
    assert gen_span.attributes is not None
    assert gen_span.attributes["pulse.match_id"] == "test_span_match"
