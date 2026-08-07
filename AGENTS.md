# AGENTS.md
> This document is the authoritative engineering guide for Ophelia.
>
> When repository code conflicts with this document,
> preserve the repository unless the user explicitly requests an architectural change.
>
> AI agents should treat this file as mandatory guidance rather than optional documentation.

# Ophelia AI Development Guide

Version: 1.0

Applies to:
- GitHub Copilot
- GitHub Copilot Agent
- ChatGPT Codex
- Claude Code
- Gemini CLI
- Continue.dev
- Aider
- Any autonomous coding agent

---

# PROJECT MISSION

Ophelia is a production-grade algorithmic cryptocurrency trading system
built specifically for BingX Perpetual Swap Futures.

The objective is NOT simply to place trades.

The objective is to build a trading platform that is:

- deterministic
- modular
- fully typed
- testable
- maintainable
- production safe

Every code change must improve the quality of the platform.

Never trade short-term convenience for long-term maintainability.

---

# PRIMARY GOALS

Every contribution should improve one or more of the following:

• correctness

• readability

• maintainability

• type safety

• reliability

• reproducibility

• operational safety

If a proposed change makes any of these worse,
do not implement it.

---

# CORE DESIGN PHILOSOPHY

Ophelia follows a layered architecture.

External systems must never leak into internal logic.

Exchange payloads are external.

Trading logic is internal.

Serialization is the boundary.

Every AI agent must preserve that boundary.

---

# ARCHITECTURE PRINCIPLE

Flow of information:

User
↓

Strategy

↓

Risk Management

↓

Order Request

↓

Validator

↓

BingXClient

↓

BingX REST API

↓

Serializer

↓

Typed Models

↓

Trading Logic

No component may bypass another layer.

---

# GOLDEN RULES

Never:

- redesign the architecture
- introduce shortcuts
- duplicate business logic
- bypass validation
- bypass serialization
- return raw exchange payloads
- add hidden state
- modify unrelated files

Always:

- preserve architecture
- preserve public APIs
- preserve strong typing
- preserve separation of concerns

---

# PROJECT STATUS

The project is currently under active development.

Architecture is considered stable.

Implementation is ongoing.

Refactoring is permitted only when explicitly requested.

Large redesigns are prohibited.

---

# CODING STANDARD

Every contribution must satisfy all of the following:

✓ readable

✓ strongly typed

✓ documented

✓ minimal

✓ deterministic

✓ testable

✓ production-safe

---

# MODIFICATION RULES

AI agents must make the smallest change necessary.

Do not refactor unrelated code.

Do not rename files without explicit permission.

Do not reorganize folders.

Do not delete existing modules unless instructed.

Do not introduce new dependencies unless requested.

---

# FILE OWNERSHIP

Each module has one responsibility.

Do not merge responsibilities.

One file should solve one problem.

Examples:

exchange/
    BingX communication only

models/
    typed data models only

strategies/
    signal generation only

portfolio/
    portfolio state only

risk/
    risk calculations only

core/
    orchestration only

utils/
    generic reusable helpers only

---

# SAFETY FIRST

This repository is intended to manage real money.

Every change must assume:

A mistake can place a live trade.

Therefore:

Prefer rejecting invalid operations over guessing.

Prefer explicit validation over implicit behavior.

Prefer failing safely over continuing with unknown state.

Never silently ignore exchange errors.

Never swallow exceptions.

Never retry order placement blindly.

Always assume financial safety is the highest priority.

---

# REPOSITORY STRUCTURE

The repository follows a layered architecture.

Every layer has a single responsibility.

Do not move responsibilities across layers.

```
app/
```

Application startup and dependency wiring.

Responsibilities:

- construct application
- dependency injection
- initialize services

Must NOT:

- contain trading logic
- call BingX directly
- implement strategies

---

```
exchange/
```

Exchange communication only.

Responsibilities:

- REST API
- request signing
- authentication
- retries
- rate limiting
- response retrieval

Must NOT:

- calculate indicators
- evaluate signals
- contain strategy logic
- make portfolio decisions

Only this layer communicates with BingX.

---

```
models/
```

Typed domain objects.

Responsibilities:

- dataclasses
- serialization targets
- immutable business objects when practical

Examples:

- Position
- OrderRequest
- OrderResponse
- Balance
- Contract
- Ticker

Models must not contain business logic.

---

```
core/
```

Business orchestration.

Coordinates the system.

Examples:

- TradingEngine
- Validator
- Scanner
- Serializer

Must never communicate with BingX directly.

Always use BingXClient.

---

```
strategies/
```

Signal generation.

A strategy answers only one question:

Should a trade be opened?

Strategies must not:

- place orders
- close orders
- modify positions
- manage risk

Strategies return signals only.

---

```
risk/
```

Risk calculations only.

Examples:

- position sizing
- leverage checks
- stop calculations
- liquidation safety

Risk modules never communicate with BingX.

---

```
portfolio/
```

Portfolio state.

Responsibilities:

- open positions
- closed positions
- exposure
- realized pnl
- unrealized pnl

Portfolio should never call the exchange.

---

```
paper/
```

Paper trading implementation.

PaperBroker should behave as closely as possible to BingX.

Differences between paper and live execution should be minimized.

---

```
dashboard/
```

Visualization only.

Never place trades.

Never modify portfolio state.

Never call exchange endpoints directly.

---

# DEPENDENCY DIRECTION

Dependencies always point downward.

Correct:

Strategy

↓

TradingEngine

↓

Validator

↓

BingXClient

Incorrect:

Strategy

↓

BingXClient

---

# IMPORT RULES

Higher layers may depend on lower layers.

Lower layers must never depend on higher layers.

Forbidden:

exchange/
imports
strategies/

Forbidden:

models/
imports
exchange/

Forbidden:

risk/
imports
dashboard/

Allowed:

TradingEngine
↓

Strategy

Allowed:

TradingEngine
↓

RiskManager

Allowed:

TradingEngine
↓

Portfolio

Allowed:

TradingEngine
↓

BingXClient

---

# SERIALIZATION BOUNDARY

Raw BingX JSON must stop inside the exchange layer.

Immediately convert responses into typed models.

Never expose raw API payloads outside exchange/ unless explicitly intended for low-level debugging.

Preferred:

REST JSON

↓

Serializer

↓

Position

↓

TradingEngine

Never:

REST JSON

↓

Strategy

---

# MODIFICATION PRIORITY

When modifying the project:

1. Preserve architecture.
2. Preserve public APIs.
3. Preserve type safety.
4. Preserve deterministic behavior.
5. Preserve backward compatibility where practical.

Only after these goals are satisfied should new features be added.

---

# WHEN IN DOUBT

If multiple implementations are possible:

Choose the one that:

- reduces coupling
- improves readability
- improves typing
- minimizes side effects
- keeps responsibilities isolated

Never optimize prematurely.

Prefer maintainability over cleverness.

---

# BINGX API CONTRACT

This repository communicates exclusively with the BingX Perpetual Futures API.

The exchange layer is the only location where HTTP requests are permitted.

Never call BingX directly from any other module.

---

# EXCHANGE LAYER

All REST communication must flow through:

exchange/BingXClient.py

Responsibilities:

- authentication
- request signing
- session management
- retries
- timeout handling
- rate limiting
- response validation
- serialization

No other module should implement HTTP requests.

---

# AUTHENTICATION

Authentication is handled only by BingXClient.

Never duplicate:

- HMAC signing
- timestamp generation
- API key injection
- session configuration

Every authenticated request must use the shared signing implementation.

---

# REQUEST FLOW

Every request follows the same lifecycle.

TradingEngine

↓

Validator

↓

BingXClient

↓

HTTP Request

↓

HTTP Response

↓

Serializer

↓

Typed Model

↓

TradingEngine

No layer may bypass another.

---

# ENDPOINT OWNERSHIP

Each endpoint should have exactly one implementation.

Correct:

BingXClient.get_balance()

Incorrect:

MarketData.get_balance()

Incorrect:

TradingEngine.get_balance()

Incorrect:

Strategy.get_balance()

---

# RAW JSON

Raw exchange payloads are external data.

They are never business objects.

Immediately convert exchange responses into typed models.

Never expose raw dictionaries outside the exchange layer unless explicitly required for debugging.

Preferred:

JSON

↓

Serializer

↓

Position

Incorrect:

JSON

↓

Strategy

---

# SERIALIZER

Serializer is the translation layer.

Responsibilities:

- normalize BingX payloads
- map JSON to models
- convert arrays to objects
- convert numeric strings
- handle optional fields

Serializer must never:

- place trades
- validate strategies
- manage portfolio

---

# VALIDATION

Every outbound request must be validated before submission.

Validator checks:

- symbol
- leverage
- quantity
- side
- position side
- stop values
- take profit
- order type

Never submit invalid requests.

Reject them early.

---

# GET REQUESTS

GET requests are safe to retry when appropriate.

Examples:

- balance
- ticker
- contracts
- positions
- klines

Retry only network failures or transient server errors.

Never hide repeated failures.

---

# POST REQUESTS

POST requests are NOT automatically safe.

Examples:

- place order
- cancel order
- close position

Never blindly retry POST requests.

Doing so may create duplicate orders.

If retries are implemented:

- use clientOrderId
- ensure idempotent behavior
- verify order status before retrying

Financial safety is more important than request completion.

---

# DELETE REQUESTS

DELETE requests should verify success before reporting completion.

Never assume success.

Always inspect the response.

---

# TIMEOUTS

Timeouts must produce explicit errors.

Never silently continue.

Never fabricate successful responses.

---

# ERROR HANDLING

Every BingX error should become a typed exception.

Examples:

AuthenticationError

RateLimitError

OrderRejected

ValidationError

NetworkError

TimeoutError

Avoid raising generic Exception where a domain-specific exception is appropriate.

---

# RATE LIMITS

Respect BingX rate limits.

Never implement busy loops.

Preferred behavior:

request

↓

429

↓

backoff

↓

retry

Avoid hammering the API.

---

# MARKET DATA

Market data must remain read-only.

Responsibilities:

- ticker
- contracts
- candles
- funding
- open interest

MarketData must never place orders.

---

# ORDER MANAGEMENT

Order placement belongs only inside the exchange layer.

Responsibilities:

- create orders
- cancel orders
- modify orders
- close positions

No strategy may submit REST requests directly.

---

# CANDLE NORMALIZATION

BingX may return candles as arrays.

Normalize every candle into a typed object before it reaches strategy logic.

Strategy code should never know the original REST payload format.

---

# VERSION DIFFERENCES

Different BingX API versions may expose different payload structures.

Normalize every version inside Serializer.

Never leak version-specific behavior into strategy logic.

Strategy code should behave identically regardless of API version.

---

# LOGGING

Log:

- endpoint
- latency
- HTTP status
- exchange code
- exchange message

Never log:

- API secrets
- signatures
- private keys
- authentication tokens

Sensitive credentials must never appear in logs.

---

# TESTABILITY

Exchange communication must remain mockable.

TradingEngine should operate correctly when BingXClient is replaced by a fake implementation.

Never tightly couple business logic to live HTTP requests.

---

# FUTURE COMPATIBILITY

Future exchange integrations should require replacing only the exchange layer.

Strategies, portfolio, risk management, and trading engine should remain exchange-independent.

---

# TYPED MODEL CONTRACT

All business objects must be represented as strongly typed models.

Never pass raw dictionaries through business logic.

Typed models define the language of the application.

---

# MODEL RESPONSIBILITIES

Models represent data.

Models do NOT perform business decisions.

Models should not:

- place trades
- call BingX
- calculate indicators
- manage positions
- perform REST requests

Models describe state only.

---

# MODEL DESIGN

Prefer:

- dataclasses
- explicit typing
- immutable fields when practical
- descriptive names

Avoid:

- Any
- dynamic attributes
- hidden state
- magic fields

Every attribute must have an explicit type.

---

# REQUIRED MODELS

The repository should expose strongly typed models for:

Balance

Contract

Ticker

Position

OrderRequest

OrderResponse

Trade

TradeFill

Kline

Account

Leverage

Margin

Funding

Additional models should follow the same conventions.

---

# FROM_API()

Every exchange model should expose:

from_api()

Example:

REST JSON

↓

Position.from_api()

↓

Position

Never deserialize inside business logic.

---

# TO_API()

Request models may expose:

to_api()

Example:

OrderRequest

↓

to_api()

↓

Dictionary

↓

BingXClient

Business logic should never manually build REST payloads.

---

# SERIALIZATION RULE

Only Serializer and model conversion methods may understand BingX payload structure.

Business logic must never depend on JSON field names.

Correct:

Position.average_price

Incorrect:

position["avgPrice"]

---

# OPTIONAL FIELDS

Exchange APIs evolve.

Models should gracefully support optional fields.

Use explicit defaults.

Never assume every key exists.

---

# TYPE CONVERSION

Convert immediately.

Examples:

"123.45"

↓

123.45

"20"

↓

20

Never leave numeric values as strings.

---

# ENUMS

Avoid magic strings.

Preferred:

OrderSide.BUY

instead of

"BUY"

Preferred:

PositionSide.LONG

instead of

"LONG"

Use Enum whenever values are finite.

---

# MODEL VALIDATION

Models should reject impossible states.

Examples:

negative quantity

invalid leverage

missing symbol

unknown side

Invalid objects should never enter business logic.

---

# IMMUTABILITY

Prefer immutable models for:

Orders

Trades

Contracts

Ticker

Market Data

Mutable models should be limited to objects whose state naturally changes.

Examples:

Portfolio

PaperPosition

TradingSession

---

# EQUALITY

Dataclasses should compare by value.

Avoid custom equality unless required.

---

# STRING REPRESENTATION

Every important model should provide useful debugging output.

Readable:

Position(
    symbol="BTC-USDT",
    side=LONG,
    quantity=0.01
)

Not:

<Position object at 0x7F2A...>

---

# MODEL SIZE

Keep models focused.

Large models should be decomposed.

Avoid "God Objects."

---

# MODEL OWNERSHIP

Each model owns its own conversion logic.

Example:

Position.from_api()

Balance.from_api()

Contract.from_api()

Avoid placing conversion logic in unrelated modules.

---

# VERSION COMPATIBILITY

Models should normalize differences between API versions.

Business logic should never know whether data came from:

V2

V3

future versions

Normalization belongs inside conversion.

---

# NO HIDDEN BEHAVIOR

Models should be predictable.

Constructors should not:

- place trades
- perform validation against the exchange
- execute HTTP requests

Construction must remain lightweight.

---

# MODEL TESTING

Every model should have unit tests verifying:

- parsing
- optional fields
- missing fields
- invalid fields
- serialization
- equality
- string representation

---

# FUTURE EXPANSION

When adding new models:

- keep naming consistent
- use dataclasses
- preserve typing
- add from_api()
- add tests
- document fields
- avoid duplicate concepts

---

# TRADING ENGINE CONTRACT

TradingEngine is the central coordinator of Ophelia.

It orchestrates the trading system.

It does NOT contain strategy logic.

It does NOT communicate directly with REST endpoints.

Its responsibility is coordination.

---

# TRADING ENGINE RESPONSIBILITIES

TradingEngine is responsible for:

- scheduling
- orchestration
- scanner execution
- strategy execution
- portfolio updates
- risk checks
- order submission
- position monitoring

TradingEngine should remain thin.

Business logic belongs elsewhere.

---

# SIGNAL LIFECYCLE

Every trade begins with a signal.

Signal

↓

Validation

↓

Risk

↓

Order Request

↓

Exchange

↓

Serializer

↓

Portfolio

Never skip a stage.

---

# STRATEGIES

A strategy generates signals only.

Strategies answer one question:

Should a position be opened?

Strategies must never:

- place orders
- close positions
- manage stops
- modify portfolio
- calculate position size
- communicate with BingX

Strategies return typed signals.

Nothing more.

---

# STRATEGY INPUT

Strategies consume:

- candles
- indicators
- market data

Strategies should never receive:

REST payloads

raw dictionaries

HTTP responses

API clients

---

# STRATEGY OUTPUT

Preferred output:

TradeSignal

Example fields:

- symbol

- side

- confidence

- timestamp

- reason

Never return raw dictionaries.

---

# SCANNER

Scanner evaluates strategies.

Responsibilities:

- fetch market data
- execute strategies
- collect signals

Scanner must not:

- place trades
- calculate risk
- modify portfolio

---

# VALIDATION

Every signal must pass validation.

Validator confirms:

- supported symbol
- valid timeframe
- quantity
- leverage
- stop values
- take profit values

Invalid signals never reach the exchange.

---

# RISK MANAGER

RiskManager decides whether a trade is allowed.

Responsibilities:

- exposure
- leverage
- position sizing
- liquidation safety
- maximum positions
- drawdown limits

RiskManager never generates signals.

RiskManager never submits orders.

---

# POSITION SIZING

Position size belongs only inside RiskManager.

Never calculate position size inside:

Strategy

TradingEngine

Portfolio

PaperBroker

---

# ORDER CREATION

OrderRequest should be built after:

signal

↓

validation

↓

risk

↓

OrderRequest

↓

BingXClient

---

# PORTFOLIO

Portfolio represents current account state.

Responsibilities:

- open positions
- closed positions
- realized pnl
- unrealized pnl
- exposure
- statistics

Portfolio should not communicate with BingX.

---

# POSITION MANAGER

PositionManager manages existing positions.

Responsibilities:

- stop updates
- trailing stop
- take profit
- breakeven
- position close

PositionManager does not generate entries.

---

# PAPER BROKER

PaperBroker should mimic BingX.

Differences should be minimal.

PaperBroker should:

- fill orders
- maintain positions
- calculate pnl
- simulate fees
- simulate leverage

PaperBroker should expose the same interface as BingXClient whenever practical.

---

# ORDER LIFECYCLE

Signal

↓

Validated

↓

Risk Approved

↓

OrderRequest

↓

Exchange

↓

OrderResponse

↓

Portfolio Update

↓

Position Monitoring

↓

Exit Signal

↓

Close Position

↓

Trade Journal

Never skip intermediate stages.

---

# POSITION LIFECYCLE

Open

↓

Active

↓

Protected

↓

Trailing

↓

Closing

↓

Closed

Every state transition should be explicit.

---

# REVERSALS

If strategy supports reversals:

LONG

↓

Close LONG

↓

Confirm close

↓

Open SHORT

Never assume the first order succeeded.

---

# TRAILING STOPS

Trailing logic belongs inside PositionManager.

Strategies should not modify trailing stops.

---

# EXIT LOGIC

Exit decisions may originate from:

- strategy
- stop loss
- take profit
- trailing stop
- liquidation prevention
- manual intervention

All exits follow the same order submission pipeline.

---

# MARKET DATA

TradingEngine never manipulates raw candles.

MarketData normalizes:

- candles
- ticker
- funding
- contracts

Strategies consume normalized data only.

---

# STATE MANAGEMENT

Avoid hidden global state.

Prefer explicit state objects.

Every position should have a single owner.

---

# CONCURRENCY

If concurrency is introduced:

Protect:

- portfolio
- positions
- order queue

Avoid race conditions.

Never allow duplicate order submission.

---

# LOGGING

Every significant trading event should be logged.

Examples:

Signal generated

Risk rejected

Order submitted

Order rejected

Position opened

Position closed

Trailing updated

Never log secrets.

---

# FAILURE HANDLING

Failures should be explicit.

Examples:

Network failure

↓

Retry if safe

↓

Abort if unsafe

↓

Log

↓

Notify

Never silently ignore failures.

---

# LIVE TRADING

LIVE_TRADING is disabled by default.

AI agents must never enable live trading.

Any change affecting live execution requires explicit user approval.

---

# FUTURE FEATURES

Future additions should integrate through existing contracts.

Do not bypass:

TradingEngine

Validator

RiskManager

Serializer

Portfolio

Maintain the architecture as the system grows.

---

# DEVELOPMENT WORKFLOW

All development must follow a predictable workflow.

The objective is reliability rather than speed.

Never sacrifice code quality for faster implementation.

---

# TASK SIZE

AI agents should complete one logical task at a time.

Examples of good tasks:

- Fix one MyPy error
- Implement one model
- Implement one endpoint
- Update one strategy
- Add one unit test
- Fix one bug

Avoid:

- "Fix the whole repository"
- "Rewrite everything"
- Large unrelated refactors

---

# BEFORE WRITING CODE

Before making changes, understand:

- the affected module
- dependencies
- public API
- existing architecture

Read surrounding code before editing.

Never assume.

---

# CHANGE SCOPE

Modify only files required for the requested task.

Avoid touching unrelated files.

Small pull requests are preferred.

---

# PUBLIC API

Public APIs are considered stable.

Never rename:

- public classes
- public methods
- public modules

unless explicitly instructed.

Backward compatibility is preferred.

---

# BRANCH STRATEGY

Every feature should have its own branch.

Example:

feature/market-data

feature/risk-manager

fix/mypy-position

fix/order-validation

Avoid committing unrelated work together.

---

# COMMITS

Commits should represent one logical change.

Good:

Fix Position.from_api parsing

Add trailing stop validation

Implement FundingRate model

Bad:

Misc fixes

Updates

Changes

---

# PULL REQUESTS

One pull request should solve one problem.

Every PR should include:

- purpose
- affected modules
- testing performed
- remaining work

Large PRs should be avoided.

---

# CODE STYLE

Follow existing repository style.

Prefer consistency over personal preference.

Do not introduce a new coding style.

---

# TYPE HINTS

Every new function must include type hints.

Avoid:

Any

Prefer:

Optional

Literal

Enum

Typed dataclasses

Protocols where appropriate

---

# DOCUMENTATION

Public classes should include docstrings.

Public methods should explain:

- purpose
- arguments
- return value

Complex algorithms should explain reasoning.

Avoid redundant comments.

---

# LOGGING

Log meaningful events.

Do not log every line.

Logs should help diagnose failures.

Never expose:

API keys

Secrets

Private tokens

Signatures

Passwords

---

# TESTING

When modifying behavior:

Update or add tests.

Verify:

happy path

edge cases

invalid input

error handling

Avoid reducing test coverage.

---

# STATIC ANALYSIS

Before considering work complete:

Run:

ruff check .

Run:

mypy .

Run:

pytest

when applicable.

Resolve new warnings before submission.

---

# PERFORMANCE

Do not optimize prematurely.

Correctness comes first.

Optimize only when:

- measured
- justified
- documented

---

# DEPENDENCIES

Avoid adding third-party libraries.

Before introducing a dependency:

Ask:

Can the standard library solve this?

Minimize dependency footprint.

---

# ERROR HANDLING

Never hide exceptions.

Raise meaningful domain-specific exceptions.

Avoid generic Exception.

Prefer:

ValidationError

OrderRejected

AuthenticationError

PositionError

etc.

---

# CODE REVIEW CHECKLIST

Before considering a task complete:

✓ Architecture preserved

✓ Public API preserved

✓ Type hints complete

✓ Validation maintained

✓ Serializer unchanged unless required

✓ No duplicate code introduced

✓ No unrelated refactoring

✓ Ruff passes

✓ MyPy passes

✓ Tests updated if needed

---

# DEFINITION OF DONE

A task is complete only if:

- implementation finished
- code reviewed
- static analysis clean
- tests updated
- documentation updated if required
- no architectural violations introduced

Working code alone is not sufficient.

---

# AI AGENT OPERATING RULES

This section defines how AI coding agents must behave while working on
the Ophelia repository.

These rules override convenience.

Never optimize for speed at the expense of correctness.

---

# GENERAL BEHAVIOR

AI agents are contributors.

Not architects.

Do not redesign the repository unless explicitly instructed.

Improve the implementation.

Preserve the design.

---

# UNDERSTAND BEFORE EDITING

Before modifying a file:

Read:

- the entire file
- dependent modules
- imported models
- related interfaces

Never edit code based on assumptions.

Always understand surrounding context first.

---

# THINK BEFORE CODING

Before writing code ask:

What is the smallest correct solution?

Can this reuse existing code?

Will this introduce duplication?

Will this violate architecture?

Will this break compatibility?

Only after answering these questions should implementation begin.

---

# MINIMUM CHANGE PRINCIPLE

Always make the smallest change necessary.

Avoid:

large refactors

renaming files

moving folders

changing architecture

unless explicitly requested.

---

# DO NOT GUESS

If information is missing:

Stop.

State what is missing.

Request clarification.

Never invent:

API fields

exchange responses

business rules

configuration values

---

# NO SILENT CHANGES

Never change behavior unless requested.

Examples:

changing leverage

changing stop logic

changing default symbols

changing retry counts

changing risk calculations

These require explicit approval.

---

# PREFER EXISTING CODE

Before writing new code:

Search for an existing implementation.

Reuse it whenever practical.

Avoid duplicate utilities.

Avoid duplicate models.

Avoid duplicate validation.

---

# FILE OWNERSHIP

Respect module boundaries.

Example:

Serializer owns serialization.

Validator owns validation.

Strategy owns signals.

RiskManager owns sizing.

TradingEngine owns orchestration.

Portfolio owns positions.

Never move responsibilities across modules.

---

# AVOID ARCHITECTURAL DRIFT

If multiple implementations exist:

Prefer the established architecture.

Do not introduce a second implementation.

Consolidation should happen only when explicitly requested.

---

# EXPLAIN MAJOR CHANGES

When making significant modifications:

Explain:

why

what changed

impact

remaining work

Never leave large unexplained edits.

---

# PULL REQUEST SIZE

Preferred:

100–400 lines

Acceptable:

400–800 lines

Avoid:

1000+ line PRs

Break large work into multiple PRs.

---

# SAFE REFACTORING

Refactor only when:

behavior remains identical

tests continue to pass

architecture improves

Avoid cosmetic refactoring.

---

# DUPLICATE CODE

Remove duplication only when:

the duplicated logic is clearly identical

shared abstraction improves readability

Do not create abstractions prematurely.

---

# STATIC ANALYSIS

Never ignore Ruff or MyPy warnings.

Do not suppress errors unless justified.

Avoid:

type: ignore

noqa

disable comments

unless absolutely necessary.

---

# COMMENTS

Write comments explaining:

intent

reasoning

constraints

Avoid comments that merely repeat the code.

---

# TESTS

Never modify production behavior solely to satisfy a failing test.

Update tests when APIs intentionally change.

If tests reveal a bug:

Fix the bug.

Do not weaken the tests.

---

# ERROR MESSAGES

Errors should help developers.

Good:

"Order quantity must be greater than zero."

Bad:

"Invalid."

Include useful context.

---

# SECURITY

Never:

log secrets

print API keys

print signatures

store secrets in source code

commit .env

Always assume repositories may become public.

---

# LIVE TRADING SAFETY

Any change affecting live trading requires explicit user approval.

Never enable:

LIVE_TRADING=True

Never remove:

validation

risk checks

confirmation steps

Never bypass:

RiskManager

Validator

Serializer

---

# FINANCIAL SAFETY

Financial correctness takes priority over software elegance.

Reject uncertain operations.

Never guess order quantities.

Never fabricate exchange responses.

Never assume order success.

Verify every critical operation.

---

# WHEN CONFLICTS EXIST

Priority order:

1. Financial safety

2. Correctness

3. Architecture

4. Type safety

5. Maintainability

6. Performance

Never sacrifice higher priorities for lower ones.

---

# COMPLETION CHECKLIST

Before declaring a task complete:

✓ Scope respected

✓ Architecture preserved

✓ Public APIs preserved

✓ Strong typing maintained

✓ Validation preserved

✓ Serialization preserved

✓ No duplicate code

✓ Ruff clean

✓ MyPy clean

✓ Tests updated if required

✓ Documentation updated if required

Only then is the task considered complete.

---

# PRODUCTION, PERFORMANCE & SECURITY STANDARDS

This repository is intended to evolve into a production-grade automated
trading platform.

Every implementation should move the project closer to production quality.

Never reduce operational safety.

---

# PRODUCTION READINESS

Production readiness requires:

- deterministic behavior
- repeatable execution
- strong typing
- reliable logging
- explicit validation
- comprehensive testing

Never merge experimental behavior into the main execution path.

---

# LIVE TRADING

LIVE_TRADING must remain disabled by default.

Changing live trading behavior requires explicit user approval.

AI agents must never:

- enable live trading
- disable safety checks
- bypass validation
- bypass RiskManager
- bypass Portfolio updates

Financial safety always takes priority.

---

# CONFIGURATION

Configuration belongs in configuration files.

Avoid:

hardcoded API keys

hardcoded secrets

hardcoded account identifiers

hardcoded URLs when configurable

Environment variables should be used whenever practical.

---

# ENVIRONMENT VARIABLES

Sensitive values include:

- API keys
- Secret keys
- Telegram tokens
- Database passwords
- Private endpoints

Never:

print them

log them

commit them

embed them in source code

Always use:

.env

or environment variables.

---

# LOGGING

Logs should be useful for diagnosing failures.

Log:

application start

shutdown

exchange requests

exchange failures

order lifecycle

position lifecycle

exceptions

Avoid excessive debug logging in production.

Never log secrets.

---

# EXCEPTIONS

Every unexpected failure should produce:

- a meaningful exception
- useful logging
- enough context for debugging

Avoid generic Exception.

Prefer domain-specific exceptions.

---

# PERFORMANCE

Correctness is more important than speed.

Optimize only after measuring.

Avoid premature optimization.

When optimization is necessary:

measure

benchmark

document

verify correctness

---

# MEMORY

Avoid unnecessary object creation.

Reuse immutable objects when practical.

Avoid hidden caches unless justified.

---

# CONCURRENCY

If multithreading or async execution is introduced:

Protect:

Portfolio

PositionManager

Order Queue

Trading Session

Avoid race conditions.

Never submit duplicate orders.

---

# NETWORKING

Network failures are expected.

Implement:

timeouts

retry policies

backoff

typed exceptions

Never assume successful communication.

---

# DEPENDENCIES

Every dependency increases maintenance cost.

Before adding a dependency ask:

Can the standard library solve this?

Can an existing dependency solve this?

Prefer minimal dependency count.

---

# CI/CD

Every pull request should eventually run:

ruff

↓

mypy

↓

pytest

↓

build validation

Failures should block merges.

---

# TESTING LEVELS

Preferred testing hierarchy:

Unit Tests

↓

Integration Tests

↓

Paper Trading

↓

Demo Environment

↓

Live Trading

Never skip directly to live trading.

---

# PAPER TRADING

Every strategy should be validated in PaperBroker before live execution.

PaperBroker should simulate:

fees

slippage

partial fills

margin

liquidation behavior where practical

---

# RELEASES

Releases should be versioned.

Example:

v1.0.0

v1.1.0

v2.0.0

Breaking changes require a major version increment.

---

# BACKWARD COMPATIBILITY

When practical:

Preserve existing public APIs.

If breaking changes are necessary:

Document them.

Explain migration.

Update tests.

---

# DOCUMENTATION

Every major feature should include:

purpose

architecture

usage

limitations

Avoid undocumented behavior.

---

# SECURITY

Assume repositories may become public.

Never commit:

.env

credentials

private certificates

exchange secrets

Always review commits before pushing.

---

# RECOVERY

Failures should leave the application in a recoverable state.

Never corrupt:

Portfolio

Position state

Trade history

Order tracking

Recovery is preferred over silent failure.

---

# FUTURE DEVELOPMENT

Every new module should:

follow repository architecture

use strong typing

respect Serializer

respect Validator

respect RiskManager

include tests

include documentation

avoid duplicate implementations

Maintain consistency as the codebase grows.

---

# MASTER AI CHECKLIST

Before completing ANY task, every AI agent must verify the following.

If any answer is NO, the task is NOT complete.

---

## UNDERSTANDING

□ I fully understood the requested task.

□ I reviewed the affected modules.

□ I understood existing architecture.

□ I avoided making assumptions.

---

## ARCHITECTURE

□ Architecture remains unchanged unless explicitly requested.

□ Responsibilities remain in the correct modules.

□ No architectural shortcuts were introduced.

□ No duplicate implementations were created.

---

## CODE QUALITY

□ Code is readable.

□ Code is strongly typed.

□ Code follows repository conventions.

□ Public APIs remain compatible.

□ No unnecessary complexity was introduced.

---

## MODELS

□ Typed models were preserved.

□ No raw exchange JSON leaked into business logic.

□ Serialization remains centralized.

□ Validation remains centralized.

---

## EXCHANGE

□ BingX communication remains inside exchange/.

□ Authentication remains centralized.

□ Request signing remains centralized.

□ POST requests are not blindly retried.

□ Exchange errors remain typed.

---

## TRADING

□ Strategies generate signals only.

□ RiskManager owns risk decisions.

□ Portfolio owns portfolio state.

□ PositionManager owns position management.

□ TradingEngine remains an orchestrator.

---

## SAFETY

□ Financial safety was preserved.

□ Validation was not bypassed.

□ Risk checks remain active.

□ LIVE_TRADING was not enabled.

□ Secrets remain protected.

---

## TESTING

□ Existing tests still make sense.

□ New behavior has tests when appropriate.

□ Edge cases were considered.

□ Error handling was verified.

---

## STATIC ANALYSIS

□ Ruff passes.

□ MyPy passes.

□ No unnecessary ignores were added.

□ No warnings were hidden.

---

## DOCUMENTATION

□ Public interfaces remain documented.

□ Complex logic is explained.

□ New behavior is documented where appropriate.

---

## PULL REQUEST

□ The PR solves one logical problem.

□ No unrelated files were modified.

□ Commit message is meaningful.

□ Changes are easy to review.

---

## PERFORMANCE

□ No unnecessary allocations.

□ No unnecessary dependencies.

□ No premature optimization.

□ Performance remains acceptable.

---

## SECURITY

□ No secrets were committed.

□ No credentials were logged.

□ No API keys were exposed.

□ Sensitive data remains protected.

---

## FINAL QUESTION

Before declaring the task complete ask:

Would I be comfortable deploying this code to a production trading system managing real money?

If the answer is NO,

the task is NOT complete.

---

# END OF AGENTS GUIDE

# Revision History

## Version 1.0

- Initial engineering handbook.
- Repository architecture defined.
- AI development workflow defined.
- Trading contracts defined.
- Production safety standards defined.