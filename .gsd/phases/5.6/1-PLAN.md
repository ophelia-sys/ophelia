---
phase: 5.6
plan: 1
wave: 1
depends_on: []
files_modified:
  - docs/PHASE_5_5_RESOURCE_OPTIMIZATION_REPORT.md
  - OPHELIA_TIMESFM.md
  - control_plane/config.py
  - control_plane/db.py
  - models/instrument.py
  - control_plane/instruments.py
  - tests/test_instrument_resolution.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "Numerical tolerance of 0.0039 between 1T and 2T is properly documented as floating-point reduction order difference and not machine epsilon"
    - "Resource contention description updated to MATERIALLY_REDUCED"
    - "DEFAULT_MAX_OPEN_TRADES is restored to intended default of 4"
    - "Ollama dependency is documented as RETAINED_AND_ISOLATED for advisory ML explanations"
    - "CanonicalInstrument model defines all 17 authoritative fields"
    - "InstrumentResolver queries live BingX contracts and resolves Crypto, US Equities, and Commodities dynamically"
    - "NFLX resolves dynamically to NCSKNETFLIX2USD-USDT without hardcoded symbol checks"
  artifacts:
    - "models/instrument.py exists and exports CanonicalInstrument"
    - "control_plane/instruments.py exists and exports CanonicalInstrument and InstrumentResolver"
    - "tests/test_instrument_resolution.py passes"
---

# Plan 5.6.1: Phase 5.5 Corrections & Canonical Instrument Model

<objective>
Complete the three Phase 5.5 corrections (numerical tolerance terminology, resource contention terminology, DEFAULT_MAX_OPEN_TRADES restoration, and Ollama audit) and implement the Canonical Instrument Model and dynamic BingX InstrumentResolver.
</objective>

<context>
- PROJECT_RULES.md
- AGENTS.md
- docs/PHASE_5_5_RESOURCE_OPTIMIZATION_REPORT.md
- OPHELIA_TIMESFM.md
- control_plane/config.py
- control_plane/us_market.py
- control_plane/symbols.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Phase 5.5 Corrections & Ollama Audit Documentation</name>
  <files>
    docs/PHASE_5_5_RESOURCE_OPTIMIZATION_REPORT.md
    OPHELIA_TIMESFM.md
    control_plane/config.py
  </files>
  <action>
    1. In docs/PHASE_5_5_RESOURCE_OPTIMIZATION_REPORT.md and OPHELIA_TIMESFM.md:
       - Replace "within fp32 eps" with explicit NUMERICAL_EQUIVALENCE_TOLERANCE = 0.0039, justified by non-associative OpenMP floating-point accumulation order across 512-point transformer reductions.
       - Replace "RESOURCE_CONTENTION_ANALYSIS: ELIMINATED" with "RESOURCE_CONTENTION_ANALYSIS: MATERIALLY_REDUCED".
    2. In control_plane/config.py:
       - Restore DEFAULT_MAX_OPEN_TRADES = int(os.environ.get("OPH_DEFAULT_MAX_OPEN_TRADES", "4")) from 2.
    3. Document Ollama audit findings in the report: Ollama is RETAINED_AND_ISOLATED. It is required for ML setup advisory reasoning and Telegram NLP, but kept strictly out of deterministic execution.
  </action>
  <verify>
    python -c "from control_plane import config; assert config.DEFAULT_MAX_OPEN_TRADES == 4, 'Cap must be 4'"
  </verify>
  <done>
    Terminology updated, trade limit restored to 4, Ollama audit documented.
  </done>
</task>

<task type="auto">
  <name>Task 2: Canonical Instrument Model & Dynamic BingX Resolver</name>
  <files>
    models/instrument.py
    control_plane/instruments.py
    tests/test_instrument_resolution.py
  </files>
  <action>
    1. Create models/instrument.py:
       - Dataclass CanonicalInstrument with: display_symbol, internal_instrument_id, asset_class, venue, venue_product, venue_symbol, quote_currency, order_endpoint, market_data_symbol, price_precision, quantity_precision, min_order_size, min_notional, leverage_rules, trading_status, source, discovery_timestamp, last_refreshed.
    2. Create control_plane/instruments.py:
       - InstrumentResolver querying BingX /openApi/swap/v2/quote/contracts.
       - 10-minute caching with explicit TTL and thread-safe invalidation.
       - Segregated resolvers for CRYPTO, US_EQUITY, and COMMODITIES.
       - Generic alias and display name resolution matching NFLX -> NCSKNETFLIX2USD-USDT, AAPL -> NCSKAAPL2USD-USDT, NVDA -> NCSKNVDA2USD-USDT, BTC -> BTC-USDT, GOLD -> NCCOGOLD2USD-USDT, SILVER -> NCCOXAG2USD-USDT.
       - NO hardcoded if-symbol=='NFLX' branches.
    3. Create tests/test_instrument_resolution.py verifying resolution, alias mapping, and error handling for missing symbols.
  </action>
  <verify>
    pytest tests/test_instrument_resolution.py -v
  </verify>
  <done>
    CanonicalInstrument implemented and tested across Crypto, US Equities, and Commodities with dynamic venue discovery.
  </done>
</task>

</tasks>

<verification>
After tasks, verify:
- [ ] config.DEFAULT_MAX_OPEN_TRADES == 4
- [ ] CanonicalInstrument model valid and importable
- [ ] Dynamic resolution for NFLX, AAPL, NVDA, BTC, GOLD, and SILVER verified
- [ ] All tests in tests/test_instrument_resolution.py pass
</verification>

<success_criteria>
- [ ] Phase 5.5 corrections complete
- [ ] Canonical instrument model implemented
- [ ] Generic resolver passes unit tests
</success_criteria>
